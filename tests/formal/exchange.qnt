/// アプリ認証とシステム認証
/// アプリ認証とシステム認証のトークン交換について、本人の認証情報の有無とシークレットの有効性を扱う。
module exchange {
  var mode: str
  var identity: bool
  var secretValid: bool
  var response: int
  action init = all { mode' = "app", identity' = true, secretValid' = true, response' = 200 }
  action request(kind: str, user: bool, secret: bool): bool = all {
    mode' = kind, identity' = user, secretValid' = secret,
    response' = if (not(secret) or (kind == "app" and not(user))) 401
                else if (kind == "system" and user) 400 else 200
  }
  action step = {
    nondet m = Set("app", "system").oneOf()
    nondet u = Bool.oneOf()
    nondet s = Bool.oneOf()
    request(m, u, s)
  }
  /// トークン交換が成功する場合、シークレットは有効で、アプリ認証では本人の認証情報があり、システム認証では本人の認証情報がない。
  val safe = response == 200 implies (secretValid and ((mode == "app") == identity))
  run exchangeTest = init.then(request("app",false,true)).then(request("app",true,false))
    .then(request("system",false,true)).then(request("system",true,true)).then(request("system",false,false))
}
