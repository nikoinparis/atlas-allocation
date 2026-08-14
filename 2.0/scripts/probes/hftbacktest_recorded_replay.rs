use std::error::Error;

use hftbacktest::{
    backtest::{
        Backtest, DataSource, ExchangeKind, L2AssetBuilder,
        assettype::LinearAsset,
        data::Data,
        models::{CommonFees, ConstantLatency, RiskAdverseQueueModel, TradingValueFeeModel},
    },
    depth::{HashMapMarketDepth, MarketDepth},
    prelude::{Bot, Event},
    types::{BUY_EVENT, DEPTH_EVENT, EXCH_EVENT, LOCAL_EVENT, SELL_EVENT, TRADE_EVENT},
};

const FIXTURE: &str = include_str!("fixtures/btcusdt_docs_excerpt.csv");

#[derive(Clone, Debug)]
struct RawRow {
    source_seq: usize,
    side: &'static str,
    kind: &'static str,
    exch_ts: i64,
    local_ts: i64,
    px: f64,
    qty: f64,
}

fn parse_fixture() -> Vec<RawRow> {
    FIXTURE
        .lines()
        .skip(1)
        .filter(|line| !line.trim().is_empty())
        .map(|line| {
            let fields: Vec<&str> = line.split(',').collect();
            assert_eq!(7, fields.len());
            RawRow {
                source_seq: fields[0].parse().unwrap(),
                side: match fields[1] {
                    "buy" => "buy",
                    "sell" => "sell",
                    other => panic!("unexpected side: {other}"),
                },
                kind: match fields[2] {
                    "depth" => "depth",
                    "trade" => "trade",
                    other => panic!("unexpected kind: {other}"),
                },
                exch_ts: fields[3].parse().unwrap(),
                local_ts: fields[4].parse().unwrap(),
                px: fields[5].parse().unwrap(),
                qty: fields[6].parse().unwrap(),
            }
        })
        .collect()
}

fn base_flags(row: &RawRow) -> u64 {
    let side = if row.side == "buy" { BUY_EVENT } else { SELL_EVENT };
    let kind = if row.kind == "depth" { DEPTH_EVENT } else { TRADE_EVENT };
    side | kind
}

fn event(row: &RawRow, venue: u64) -> Event {
    Event {
        ev: base_flags(row) | venue,
        exch_ts: row.exch_ts,
        local_ts: row.local_ts,
        px: row.px,
        qty: row.qty,
        order_id: 0,
        ival: 0,
        fval: 0.0,
    }
}

fn validate_source(rows: &[RawRow]) -> usize {
    assert_eq!(23, rows.len());
    let mut inversions = 0;
    for (index, row) in rows.iter().enumerate() {
        assert_eq!(index + 1, row.source_seq);
        assert!(row.px.is_finite() && row.px > 0.0);
        assert!(row.qty.is_finite() && row.qty >= 0.0);
        assert!(row.kind != "trade" || row.qty > 0.0);
        assert!(row.exch_ts <= row.local_ts);
        if index > 0 {
            assert!(rows[index - 1].local_ts <= row.local_ts);
            if rows[index - 1].exch_ts > row.exch_ts {
                inversions += 1;
            }
        }
    }
    inversions
}

fn corrected_events(rows: &[RawRow]) -> Vec<Event> {
    let mut result = Vec::new();
    let depth: Vec<&RawRow> = rows.iter().filter(|row| row.kind == "depth").collect();
    let trades: Vec<&RawRow> = rows.iter().filter(|row| row.kind == "trade").collect();

    for row in &depth {
        result.push(event(row, EXCH_EVENT));
    }
    for row in trades.iter().filter(|row| row.exch_ts < depth[0].local_ts && row.source_seq < 3) {
        result.push(event(row, EXCH_EVENT | LOCAL_EVENT));
    }
    for row in &depth {
        result.push(event(row, LOCAL_EVENT));
    }
    for row in trades.iter().filter(|row| row.source_seq > 21) {
        result.push(event(row, EXCH_EVENT | LOCAL_EVENT));
    }
    result
}

fn size_guard(qty: f64, visible_qty: f64) -> bool {
    qty.is_finite() && qty > 0.0 && visible_qty.is_finite() && qty <= visible_qty
}

#[test]
fn recorded_documentation_excerpt_replays_with_platform_guards() -> Result<(), Box<dyn Error>> {
    let rows = parse_fixture();
    let inversions = validate_source(&rows);
    assert_eq!(1, inversions, "the fixture must retain the documented timestamp inversion");

    let events = corrected_events(&rows);
    assert_eq!(42, events.len());
    let data = Data::from_data(&events);
    let mut backtest = Backtest::builder()
        .add_asset(
            L2AssetBuilder::new()
                .data(vec![DataSource::Data(data)])
                .parallel_load(false)
                .latency_model(ConstantLatency::new(10_000_000, 10_000_000))
                .asset_type(LinearAsset::new(1.0))
                .fee_model(TradingValueFeeModel::new(CommonFees::new(0.0002, 0.0005)))
                .exchange(ExchangeKind::PartialFillExchange)
                .queue_model(RiskAdverseQueueModel::new())
                .last_trades_capacity(16)
                .depth(|| HashMapMarketDepth::new(0.1, 0.001))
                .build()?,
        )
        .build()?;

    backtest.goto_end()?;
    let depth = backtest.depth(0);
    let best_bid = depth.best_bid();
    let best_ask = depth.best_ask();
    let best_bid_qty = depth.best_bid_qty();
    let best_ask_qty = depth.best_ask_qty();

    assert!((best_bid - 22183.4).abs() < 1e-9);
    assert!((best_ask - 22194.3).abs() < 1e-9);
    assert!((best_bid_qty - 0.014).abs() < 1e-12);
    assert!((best_ask_qty - 0.270).abs() < 1e-12);
    assert_eq!(4, backtest.last_trades(0).len());
    assert!(size_guard(0.1, best_ask_qty));
    assert!(!size_guard(0.5, best_ask_qty));
    assert!(!size_guard(f64::NAN, best_ask_qty));

    let state = backtest.state_values(0);
    assert_eq!(0, state.num_trades);
    assert!(state.balance.is_finite() && state.fee.is_finite() && state.position.is_finite());
    println!(
        "REPLAY_METRICS {{\"source_rows\":23,\"engine_events\":42,\"timestamp_inversions\":1,\"market_trades\":4,\"best_bid\":{best_bid},\"best_ask\":{best_ask},\"best_bid_qty\":{best_bid_qty},\"best_ask_qty\":{best_ask_qty},\"safe_order_qty\":0.1,\"oversized_order_qty\":0.5,\"simulated_fills\":{}}}",
        state.num_trades
    );
    backtest.close()?;
    Ok(())
}
