/// 通知の既読管理
/// 一件の全体通知について、利用者と提供者それぞれの既読状態を扱う。
module notifications {
  var sent: bool
  var seen: Set[str]
  var operation: str
  action init = all { sent' = false, seen' = Set(), operation' = "init" }
  action send = all { not(sent), sent' = true, seen' = Set(), operation' = "send" }
  action read(who: str): bool = all { sent, sent' = true, seen' = seen.union(Set(who)), operation' = who }
  action step = any { send, read("consumer"), read("provider") }
  /// 通知が送信されるまでは既読者がいない。既読者はモデル内の利用者と提供者に限られる。
  val safe = seen.subseteq(Set("consumer", "provider")) and (sent or seen == Set())
  run readTest = init.then(send).then(read("consumer")).then(read("consumer")).then(read("provider"))
}
