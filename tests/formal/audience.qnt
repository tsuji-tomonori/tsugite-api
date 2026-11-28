/// カタログの公開範囲
/// 一般公開、提供元、プロジェクト、部署の祖先所属、属性の直接所属を閲覧条件として扱う。
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
  /// 商品を閲覧できる場合は、無関係な所属、属性階層の親だけへの所属、閲覧条件なしのいずれにも当てはまらない。
  val safe = visible implies not(Set("unrelated", "attributeParent", "none").contains(source))
  run visibilityTest = init.then(selectAudience("public")).then(selectAudience("owner"))
    .then(selectAudience("project")).then(selectAudience("ancestor")).then(selectAudience("unrelated"))
    .then(selectAudience("directAttribute")).then(selectAudience("attributeParent"))
}
