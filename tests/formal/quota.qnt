// 1分に2回まで。期間境界と通知回数は独立に観測する。
module quota {
  var calls: int
  var notified: int
  var operation: str
  var response: int
  action init = all { calls' = 0, notified' = 0, operation' = "init", response' = 0 }
  action call = all {
    calls' = if (calls < 2) calls + 1 else calls,
    notified' = if (calls == 1) notified + 1 else notified,
    operation' = "invoke", response' = if (calls < 2) 200 else 429
  }
  action newWindow = all { notified < 2, calls' = 0, notified' = notified,
                           operation' = "nextWindow", response' = 0 }
  action step = any { call, newWindow }
  val safe = calls <= 2 and (response == 429 implies calls == 2)
  run thresholdTest = init.then(call).then(call).then(call).then(newWindow).then(call).then(call)
}
