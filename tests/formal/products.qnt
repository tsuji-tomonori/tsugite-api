// 同一商品の環境別の利用権。構造変更と文言変更を区別する。
module products {
  var listed: bool
  var removed: bool
  var status: str
  var operation: str
  action result(op: str, visible: bool, gone: bool, right: str): bool = all {
    operation' = op, listed' = visible, removed' = gone, status' = right
  }
  action init = all { listed' = false, operation' = "init", removed' = false, status' = "absent" }
  action submitPublication = all { not(removed), not(listed), result("submitPublication", false, false, status) }
  action publish = all { operation == "submitPublication", result("publish", true, false, status) }
  action apply = all { listed, status == "absent", result("apply", true, false, "pending") }
  action approve = all { status == "pending", result("approve", listed, false, "approved") }
  action rename = all { not(removed), result("rename", listed, false, status) }
  val closed = if (status == "approved") "revoked" else if (status == "pending") "rejected" else status
  action structural = all { not(removed), result("structure", false, false, closed) }
  action remove = all { not(removed), result("delete", false, true, closed) }
  action step = any { submitPublication, publish, apply, approve, rename, structural, remove, all { removed, result("deleted", false, true, closed) } }
  val safe = (removed implies (not(listed) and not(Set("pending","approved").contains(status)))) and
    (operation != "structure" or not(listed))
  run editTest = init.then(submitPublication).then(publish).then(apply).then(approve).then(rename).then(structural)
  run pendingEditTest = init.then(submitPublication).then(publish).then(apply).then(structural)
  run deleteTest = init.then(submitPublication).then(publish).then(apply).then(approve).then(remove)
}
