/// 商品の二段階公開承認
/// 申請者、プロジェクトリーダー、管理者による公開審査を扱う。
module publication {
  var stage: int
  var caller: str
  var response: int
  var listed: bool
  action init = all { stage' = 0, caller' = "", response' = 0, listed' = false }
  action review(by: str): bool = {
    val allowed = (stage == 0 and by == "lead") or (stage == 1 and by == "admin")
    all { stage' = if (allowed) stage + 1 else stage,
          response' = if (stage == 2) 409 else if (allowed) 200 else 403,
          caller' = by, listed' = (listed or (stage == 1 and allowed)) }
  }
  action step = { nondet by = Set("lead", "admin", "applicant").oneOf()
                  review(by) }
  /// 商品が掲載されているのは、二段階の承認が完了したときに限る。
  val safe = listed == (stage == 2)
  run orderedTest = init.then(review("admin")).then(review("applicant")).then(review("lead"))
    .then(review("lead")).then(review("admin")).then(review("admin"))
}
