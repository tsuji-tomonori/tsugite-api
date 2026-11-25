// 商品共通の属性承認と、環境別autoルートでの事前条件を確かめる。
module automatic {
  var route: str
  var consent: bool
  var matches: bool
  var response: int
  var status: str
  action apply(mode: str, terms: bool, matched: bool): bool = all {
    route' = mode, consent' = terms, matches' = matched,
    response' = if (mode == "auto" and not(terms)) 422 else 201,
    status' = if (mode == "auto" and not(terms)) "absent"
              else if (mode == "auto" or matched) "approved" else "pending"
  }
  action init = all { consent' = true, matches' = false, response' = 201, route' = "legacy", status' = "pending" }
  action step = {
    nondet mode = Set("legacy","auto").oneOf()
    nondet t = Bool.oneOf()
    nondet m = Bool.oneOf()
    apply(mode,t,m)
  }
  val safe = (route == "auto" and not(consent)) implies status == "absent"
  run autoTest = init.then(apply("legacy",true,true)).then(apply("auto",false,true)).then(apply("auto",true,false))
}
