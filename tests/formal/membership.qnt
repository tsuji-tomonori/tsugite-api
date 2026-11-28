/// 所属とリーダー権限
/// 一つのプロジェクトに対する利用者の所属と、リーダー権限の付与・解除を扱う。
module membership {
  var member: bool
  var leader: bool
  var operation: str
  action init = all { member' = false, leader' = false, operation' = "init" }
  action setMembership(manages: bool): bool = all { member' = true, leader' = manages,
                                             operation' = if (manages) "lead" else "join" }
  action leave = all { member, member' = false, leader' = false, operation' = "leave" }
  action step = any { setMembership(true), setMembership(false), leave }
  /// プロジェクトのリーダーは、そのプロジェクトに所属している。
  val safe = leader implies member
  run membershipTest = init.then(setMembership(false)).then(setMembership(true)).then(setMembership(false)).then(leave)
}
