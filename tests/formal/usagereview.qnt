// 指名された利用者から提供プロジェクトのリーダーへ、順番に審査する。
module usagereview {
  var stage: str
  var caller: str
  var response: int
  var approved: bool
  action init = all { stage' = "person/admin", caller' = "", response' = 0, approved' = false }
  action decide(by: str): bool = {
    val allowed = stage == by and not(approved)
    all { caller' = by, response' = if (allowed) 200 else if (approved and by != "person/admin") 409 else 403,
          stage' = if (not(allowed)) stage else if (stage == "person/admin") "project_leader" else "",
          approved' = (approved or (allowed and stage == "project_leader")) }
  }
  action step = { nondet by = Set("provider", "person/admin", "project_leader").oneOf()
                  decide(by) }
  val safe = approved == (stage == "")
  run orderedTest = init.then(decide("provider")).then(decide("project_leader"))
    .then(decide("person/admin")).then(decide("person/admin")).then(decide("project_leader")).then(decide("provider"))
}
