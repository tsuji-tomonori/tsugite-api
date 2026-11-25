// 時刻は発行後の秒数。個人と認証情報の両方が許す操作だけを認める。
module credentials {
  var age: int
  var projectMinutes: int
  var apiMinutes: int
  var keyAllows: bool
  var userAllows: bool
  var currentGeneration: bool
  var response: int
  action check(seconds: int, projectCap: int, apiCap: int, keyOK: bool, userOK: bool, current: bool): bool =
    all { age' = seconds, projectMinutes' = projectCap, apiMinutes' = apiCap,
          keyAllows' = keyOK, userAllows' = userOK, currentGeneration' = current,
          response' = if (seconds >= projectCap * 60 or seconds >= apiCap * 60 or not(current)) 401
                      else if (keyOK and userOK) 200 else 403 }
  action init = all { age' = 0, apiMinutes' = 60, currentGeneration' = true, keyAllows' = true, projectMinutes' = 60, response' = 200, userAllows' = true }
  action step = {
    nondet seconds = Set(0, 59, 60, 119, 120, 3600).oneOf()
    nondet projectCap = Set(1, 2, 60).oneOf()
    nondet apiCap = Set(1, 2, 60).oneOf()
    nondet keyOK = Bool.oneOf()
    nondet userOK = Bool.oneOf()
    nondet current = Bool.oneOf()
    check(seconds, projectCap, apiCap, keyOK, userOK, current)
  }
  val safe = response != 200 or (keyAllows and userAllows and currentGeneration
    and age < projectMinutes * 60 and age < apiMinutes * 60)
  run lifetimeTest = init.then(check(119, 2, 60, true, true, true)).then(check(120, 2, 60, true, true, true))
    .then(check(60, 2, 1, true, true, true)).then(check(59, 2, 1, true, true, true))
    .then(check(3600, 60, 60, true, true, true))
  run operationsTest = init.then(check(0, 60, 60, true, false, true))
    .then(check(0, 60, 60, false, true, true)).then(check(0, 60, 60, false, false, true))
  run rotatedTest = init.then(check(0, 60, 60, true, true, false))
}
