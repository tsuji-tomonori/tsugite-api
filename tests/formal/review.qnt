/// 利用申請の段階別承認
/// 環境別の利用条件、部署から提供者への承認順、申請者本人による判断を扱う。
module review {
  var status: str
  var stage: str
  var operation: str
  var response: int
  action result(op: str, code: int, grant: str, nextStage: str): bool = all {
    operation' = op, response' = code, status' = grant, stage' = nextStage
  }
  action init = all { operation' = "init", response' = 0, stage' = "", status' = "absent" }
  action submit(op: str): bool =
    if (status == "pending" or status == "approved") result(op, 409, status, stage)
    else if (op == "staleTerms") result(op, 409, status, stage)
    else if (Set("noConsent", "wrongAnswer").contains(op)) result(op, 422, status, stage)

    else result(op, 201, "pending", "department")
  action reviewAs(role: str): bool =
    all { status == "pending", if (stage != role) result(role, 403, status, stage)
    else if (role == "department") result(role, 200, "pending", "provider")
    else result(role, 200, "approved", "") }
  action call = result("invoke", if (status == "approved") 200 else 403, status, stage)
  /// 承認済みの利用申請には、未完了の承認段階が残らない。
  val safe = status != "approved" or stage == ""
  action step = any { submit("submit"), submit("staleTerms"), submit("wrongAnswer"), submit("noConsent"),
                      reviewAs("department"), reviewAs("provider"), reviewAs("applicant"), call }
  run orderedTest = init.then(submit("submit")).then(reviewAs("provider")).then(reviewAs("applicant"))
    .then(call).then(reviewAs("department")).then(call).then(reviewAs("provider")).then(call)
  run termsTest = init.then(submit("staleTerms")).then(submit("noConsent")).then(submit("wrongAnswer"))
    .then(submit("submit"))
}
