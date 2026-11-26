/// 組織の削除と移管
/// 子部署が残る組織の削除、移管先の妥当性、同じ移管操作の再試行を扱う。
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
  /// モデル内で追跡する所属先は、移管元または正規の移管先のいずれかである。
  val safe = Set("source", "successor").contains(parent)
  run transferTest = init.then(remove).then(invalid("child")).then(invalid("self"))
    .then(invalid("otherKind")).then(transfer).then(transfer)
}
