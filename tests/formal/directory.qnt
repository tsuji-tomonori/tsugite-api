// 子部署が残る組織の削除、同種の後継への移管、再試行と識別子の再利用。
module directory {
  var parent: str
  var operation: str
  var response: int
  action result(op: str, newParent: str, code: int): bool = all {
    operation' = op, parent' = newParent, response' = code
  }
  action init = all { operation' = "init", parent' = "source", response' = 0 }
  action remove = all { parent == "source", result("delete", parent, 409) }
  action invalid(target: str): bool = all { parent == "source", result(target, parent, 422) }
  action transfer = result("transfer", "successor", 200)
  action step = any { remove, invalid("child"), invalid("self"), invalid("otherKind"), transfer }
  val safe = Set("source", "successor").contains(parent)
  run transferTest = init.then(remove).then(invalid("child")).then(invalid("self"))
    .then(invalid("otherKind")).then(transfer).then(transfer)
}
