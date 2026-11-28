// 編集、取り下げ、却下で現在の審査を閉じ、再申請後に新しい審査を開始する。
module publicationchanges {
  var pending: bool
  var operation: str
  var response: int
  action init = all { pending' = false, operation' = "init", response' = 0 }
  action submit = all { pending' = true, operation' = "submit", response' = 200 }
  action close(op: str): bool = all {
    pending, pending' = false, operation' = op, response' = 200
  }
  action oldDecision = all { pending' = pending, operation' = "stale", response' = 409 }
  action step = any { submit, close("reject"), close("edit"), close("withdraw"), oldDecision }
  val safe = Set("reject", "edit", "withdraw").contains(operation) implies not(pending)
  run restartTest = init.then(submit).then(close("reject")).then(submit).then(oldDecision)
    .then(close("edit")).then(oldDecision).then(submit).then(close("withdraw")).then(oldDecision)
}
