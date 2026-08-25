# Derivatives Breadth Program V1

The futures and options upgrade is implemented only to the point justified by the
available evidence. Platform-owned contracts now require explicit futures contract
identity, expiration, bid/ask, multiplier, fees, and initial/maintenance margin, and
they book both legs of a contract roll. The options contract requires quote time,
expiration, exercise style, bid/ask, multiplier, implied volatility, Greeks, margin,
and assignment fees. Short-option sizing must pass both a declared tail-loss budget
and a broker-margin gate.

No historical return was calculated. The repository does not contain point-in-time
contract chains or option surfaces with the execution, roll, margin, and assignment
history required for a defensible test. End-of-day proxy prices would hide exactly the
risks this program is intended to measure.

Hull 11e sections 10.6-10.8, 19.6, 19.8, 19.10-19.11, and 20.5 were checked directly.
They confirm that bid/ask and exercise/assignment costs, short-option margin,
gamma/vega and scenario risk, and strike/maturity-dependent volatility surfaces must
be part of the implementation. The data blockers are frozen in
`config/derivatives_breadth_program_v1.json`; live execution remains disabled.
