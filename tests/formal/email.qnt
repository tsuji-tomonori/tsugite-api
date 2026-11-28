// 外部名簿と保存済みの本人識別子を比較し、適用時に限って連絡先を更新する。
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
  val safe = operation == "apply" implies updated
  run contactTest = init.then(sync("preview")).then(sync("mismatch")).then(sync("disabled"))
    .then(sync("retired")).then(sync("apply")).then(sync("apply"))
}
