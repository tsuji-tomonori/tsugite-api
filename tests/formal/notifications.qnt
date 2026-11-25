// 全体通知一件について受信者ごとに既読を管理する。
module notifications {
  var sent: bool
  var seen: Set[str]
  var operation: str
  action init = all { sent' = false, seen' = Set(), operation' = "init" }
  action send = all { not(sent), sent' = true, seen' = Set(), operation' = "send" }
  action read(who: str): bool = all { sent, sent' = true, seen' = seen.union(Set(who)), operation' = who }
  action step = any { send, read("consumer"), read("provider") }
  val safe = seen.subseteq(Set("consumer", "provider")) and (sent or seen == Set())
  run readTest = init.then(send).then(read("consumer")).then(read("consumer")).then(read("provider"))
}
