// 閲覧条件は論理和。部署は祖先所属を含み、任意属性は直接所属だけを使う。
module audience {
  var source: str
  var visible: bool
  action selectAudience(kind: str): bool = all {
    source' = kind,
    visible' = Set("public", "owner", "project", "ancestor", "directAttribute").contains(kind)
  }
  action init = all { source' = "none", visible' = false }
  action step = {
    nondet kind = Set("public", "owner", "project", "ancestor", "directAttribute",
                      "unrelated", "attributeParent", "none").oneOf()
    selectAudience(kind)
  }
  val safe = visible implies not(Set("unrelated", "attributeParent", "none").contains(source))
  run visibilityTest = init.then(selectAudience("public")).then(selectAudience("owner"))
    .then(selectAudience("project")).then(selectAudience("ancestor")).then(selectAudience("unrelated"))
    .then(selectAudience("directAttribute")).then(selectAudience("attributeParent"))
}
