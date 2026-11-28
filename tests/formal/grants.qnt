// 利用権の状態と、現在の操作によるHTTP応答を独立に記述する。
module grants {
  var status: str
  var listed: bool
  var operation: str
  var response: int
  var forwarded: bool
  action init = all {
    status' = "absent", listed' = true, operation' = "init", response' = 0, forwarded' = false
  }
  action move(op: str, after: str, published: bool, code: int, send: bool): bool = all {
    status' = after, listed' = published, operation' = op, response' = code, forwarded' = send
  }
  val live = Set("pending", "approved").contains(status)
  action apply = if (listed and not(live)) move("apply", "pending", listed, 201, false)
                 else move("apply", status, listed, 409, false)
  action decide(op: str, before: str, after: str): bool =
    if (status == before) move(op, after, listed, 200, false)
    else move(op, status, listed, if (status == "absent") 404 else 409, false)
  action approve = decide("approve", "pending", "approved")
  action reject = decide("reject", "pending", "rejected")
  action withdraw = decide("withdraw", "pending", "withdrawn")
  action revoke = decide("revoke", "approved", "revoked")
  action unpublish = move("unpublish", status, false, 200, false)
  action invoke(op: str): bool = {
    val send = status == "approved" and op == "invoke"
    move(op, status, listed, if (send) 200 else 403, send)
  }
  action step = any { apply, approve, reject, withdraw, revoke, unpublish,
                      invoke("invoke"), invoke("otherEnvironment"), invoke("otherProject"),
                      invoke("otherProduct") }
  val safe = not(forwarded) or (status == "approved" and operation == "invoke")
  run lifecycleTest = init.then(apply).then(invoke("invoke")).then(approve)
    .then(invoke("invoke")).then(unpublish).then(invoke("invoke")).then(revoke).then(invoke("invoke"))
  run scopeTest = init.then(apply).then(approve).then(invoke("invoke"))
    .then(invoke("otherEnvironment")).then(invoke("otherProject")).then(invoke("otherProduct"))
  run reapplyTest = init.then(apply).then(apply).then(reject).then(apply).then(withdraw)
    .then(apply).then(approve).then(approve).then(revoke).then(apply)
  run closedTest = init.then(apply).then(withdraw).then(unpublish).then(apply)
}
