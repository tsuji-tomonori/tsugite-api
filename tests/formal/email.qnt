/// 外部名簿からの連絡先同期
/// プレビュー、適用、識別子の不一致、無効化、退職を表す操作と、連絡先の更新状態を扱う。
module email {
  var updated: bool
  var operation: str
  var verified: bool
  action init = all { updated' = false, operation' = "init", verified' = false }
  action sync(op: str): bool = all {
    updated' = (updated or op == "apply"), operation' = op,
    verified' = (not(updated) and Set("apply","mismatch","disabled").contains(op))
  }
  action step = any { sync("preview"), sync("apply"), sync("mismatch"), sync("disabled"), sync("retired") }
  /// 同期の適用操作の後は、連絡先が更新済みである。
  val safe = operation == "apply" implies updated
  run contactTest = init.then(sync("preview")).then(sync("mismatch")).then(sync("disabled"))
    .then(sync("retired")).then(sync("apply")).then(sync("apply"))
}
