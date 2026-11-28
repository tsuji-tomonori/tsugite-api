// 一つのプロジェクトに対する一般利用者の現在の所属とリーダー権限。
module membership {
  var member: bool
  var leader: bool
  var operation: str
  action init = all { member' = false, leader' = false, operation' = "init" }
  action setMembership(manages: bool): bool = all { member' = true, leader' = manages,
                                             operation' = if (manages) "lead" else "join" }
  action leave = all { member, member' = false, leader' = false, operation' = "leave" }
  action step = any { setMembership(true), setMembership(false), leave }
  val safe = leader implies member
  run membershipTest = init.then(setMembership(false)).then(setMembership(true)).then(setMembership(false)).then(leave)
}
