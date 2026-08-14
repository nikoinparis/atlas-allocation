use hftbacktest::{
    backtest::{
        assettype::LinearAsset,
        models::{
            CommonFees, ConstantLatency, FeeModel, LatencyModel, RiskAdverseQueueModel,
            QueueModel, TradingValueFeeModel,
        },
        order::{order_bus, OrderBus},
        proc::{PartialFillExchange, Processor},
        state::State,
    },
    depth::{HashMapMarketDepth, L2MarketDepth},
    types::{
        Event, OrdType, Order, Side, Status, TimeInForce, EXCH_ASK_DEPTH_EVENT,
        EXCH_BID_DEPTH_EVENT, EXCH_SELL_TRADE_EVENT,
    },
};

fn order(order_id: u64, side: Side, price_tick: i64, qty: f64) -> Order {
    Order::new(
        order_id,
        price_tick,
        1.0,
        qty,
        side,
        OrdType::Limit,
        TimeInForce::GTC,
    )
}

fn event(ev: u64, ts: i64, px: f64, qty: f64) -> Event {
    Event {
        ev,
        exch_ts: ts,
        local_ts: ts,
        px,
        qty,
        order_id: 0,
        ival: 0,
        fval: 0.0,
    }
}

fn assert_close(actual: f64, expected: f64) {
    assert!((actual - expected).abs() < 1e-12, "actual={actual}, expected={expected}");
}

#[test]
fn constant_latency_and_technical_rejection_are_time_ordered() {
    let mut sample = order(1, Side::Buy, 100, 1.0);
    let mut latency = ConstantLatency::new(7, 11);
    assert_eq!(latency.entry(100, &sample), 7);
    assert_eq!(latency.response(107, &sample), 11);

    let (_exchange_bus, mut local_bus) = order_bus(ConstantLatency::new(-5, 0));
    sample.local_timestamp = 100;
    sample.req = Status::New;
    local_bus.request(sample, |rejected| rejected.req = Status::Rejected);
    assert_eq!(local_bus.earliest_recv_order_timestamp(), Some(105));
    let rejected = local_bus.receive(105).expect("rejection response");
    assert_eq!(rejected.req, Status::Rejected);
}

#[test]
fn order_bus_never_moves_a_later_append_backwards_in_time() {
    let mut bus = OrderBus::new();
    bus.append(order(1, Side::Buy, 100, 1.0), 10);
    bus.append(order(2, Side::Buy, 100, 1.0), 5);
    assert_eq!(bus.pop_front().unwrap().1, 10);
    assert_eq!(bus.pop_front().unwrap().1, 10);
}

#[test]
fn risk_adverse_queue_requires_trades_to_clear_quantity_ahead() {
    let mut depth = HashMapMarketDepth::new(1.0, 1.0);
    depth.update_bid_depth(100.0, 5.0, 0);
    let queue: RiskAdverseQueueModel<HashMapMarketDepth> = RiskAdverseQueueModel::new();
    let mut resting = order(1, Side::Buy, 100, 3.0);
    queue.new_order(&mut resting, &depth);
    queue.trade(&mut resting, 5.0, &depth);
    assert_close(queue.is_filled(&mut resting, &depth), 0.0);
    queue.trade(&mut resting, 2.0, &depth);
    assert_close(queue.is_filled(&mut resting, &depth), 2.0);
}

#[test]
fn partial_fill_exchange_reports_two_fills_and_reconciles_remaining_quantity() {
    let (exchange_bus, mut local_bus) = order_bus(ConstantLatency::new(10, 5));
    let mut exchange = PartialFillExchange::new(
        HashMapMarketDepth::new(1.0, 1.0),
        State::new(
            LinearAsset::new(1.0),
            TradingValueFeeModel::new(CommonFees::new(0.001, 0.002)),
        ),
        RiskAdverseQueueModel::new(),
        exchange_bus,
    );
    exchange.process(&event(EXCH_BID_DEPTH_EVENT, 0, 100.0, 5.0)).unwrap();
    exchange.process(&event(EXCH_ASK_DEPTH_EVENT, 0, 101.0, 5.0)).unwrap();

    let mut submitted = order(10, Side::Buy, 100, 3.0);
    submitted.req = Status::New;
    submitted.local_timestamp = 0;
    local_bus.request(submitted, |_| panic!("unexpected rejection"));
    exchange.process_recv_order(10, None).unwrap();
    let acknowledged = local_bus.receive(15).expect("new-order acknowledgement");
    assert_eq!(acknowledged.status, Status::New);

    exchange.process(&event(EXCH_SELL_TRADE_EVENT, 20, 100.0, 6.0)).unwrap();
    let first = local_bus.receive(25).expect("first partial fill");
    assert_eq!(first.status, Status::PartiallyFilled);
    assert_close(first.exec_qty, 1.0);
    assert_close(first.leaves_qty, 2.0);

    exchange.process(&event(EXCH_SELL_TRADE_EVENT, 30, 100.0, 2.0)).unwrap();
    let second = local_bus.receive(35).expect("final fill");
    assert_eq!(second.status, Status::Filled);
    assert_close(second.exec_qty, 2.0);
    assert_close(second.leaves_qty, 0.0);
    assert_close(first.exec_qty + second.exec_qty, 3.0);
}

#[test]
fn cancellation_processed_before_a_trade_prevents_a_fill() {
    let (exchange_bus, mut local_bus) = order_bus(ConstantLatency::new(10, 5));
    let mut exchange = PartialFillExchange::new(
        HashMapMarketDepth::new(1.0, 1.0),
        State::new(
            LinearAsset::new(1.0),
            TradingValueFeeModel::new(CommonFees::new(0.0, 0.0)),
        ),
        RiskAdverseQueueModel::new(),
        exchange_bus,
    );
    exchange.process(&event(EXCH_BID_DEPTH_EVENT, 0, 100.0, 1.0)).unwrap();
    exchange.process(&event(EXCH_ASK_DEPTH_EVENT, 0, 101.0, 1.0)).unwrap();

    let mut submitted = order(20, Side::Buy, 100, 1.0);
    submitted.req = Status::New;
    local_bus.request(submitted, |_| panic!("unexpected rejection"));
    exchange.process_recv_order(10, None).unwrap();
    let acknowledged = local_bus.receive(15).unwrap();

    let mut cancel = acknowledged.clone();
    cancel.req = Status::Canceled;
    cancel.local_timestamp = 20;
    local_bus.request(cancel, |_| panic!("unexpected cancellation rejection"));
    exchange.process_recv_order(30, None).unwrap();
    let canceled = local_bus.receive(35).expect("cancel response");
    assert_eq!(canceled.status, Status::Canceled);

    exchange.process(&event(EXCH_SELL_TRADE_EVENT, 40, 100.0, 5.0)).unwrap();
    assert_eq!(local_bus.earliest_recv_order_timestamp(), None);
}

#[test]
fn fees_cash_position_and_equity_reconcile_across_round_trip() {
    let mut state = State::new(
        LinearAsset::new(1.0),
        TradingValueFeeModel::new(CommonFees::new(0.001, 0.002)),
    );
    let mut buy = order(1, Side::Buy, 1000, 2.0);
    buy.tick_size = 0.01;
    buy.exec_price_tick = 1000;
    buy.exec_qty = 2.0;
    buy.maker = false;
    state.apply_fill(&buy);
    assert_close(state.values().position, 2.0);
    assert_close(state.values().balance, -20.0);
    assert_close(state.values().fee, 0.04);
    assert_close(state.equity(10.0), -0.04);

    let mut sell = order(2, Side::Sell, 1100, 2.0);
    sell.tick_size = 0.01;
    sell.exec_price_tick = 1100;
    sell.exec_qty = 2.0;
    sell.maker = true;
    state.apply_fill(&sell);
    assert_close(state.values().position, 0.0);
    assert_close(state.values().balance, 2.0);
    assert_close(state.values().fee, 0.062);
    assert_close(state.equity(11.0), 1.938);
    assert_eq!(state.values().num_trades, 2);
    assert_close(state.values().trading_volume, 4.0);
    assert_close(state.values().trading_value, 42.0);
}

#[test]
fn direct_state_api_accepts_overfill_so_platform_guard_is_required() {
    let mut state = State::new(
        LinearAsset::new(1.0),
        TradingValueFeeModel::new(CommonFees::new(0.0, 0.0)),
    );
    let mut invalid = order(1, Side::Buy, 100, 1.0);
    invalid.exec_price_tick = 100;
    invalid.exec_qty = 2.0;
    invalid.leaves_qty = -1.0;
    state.apply_fill(&invalid);
    assert_close(state.values().position, 2.0);
}

#[test]
fn nonfinite_fee_configuration_propagates_so_platform_guard_is_required() {
    let model = TradingValueFeeModel::new(CommonFees::new(f64::NAN, 0.0));
    let mut maker = order(1, Side::Buy, 100, 1.0);
    maker.exec_price_tick = 100;
    maker.exec_qty = 1.0;
    maker.maker = true;
    assert!(!model.amount(&maker, 100.0).is_finite());
}
