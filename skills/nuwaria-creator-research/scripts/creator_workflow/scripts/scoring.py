"""Evidence-backed SOP scores. Missing dimensions remain unscored."""
DIMENSIONS = {
    'natural_seeding': ('自然植入', 25), 'brand_fit': ('品牌适配', 20),
    'conversion': ('转化能力', 20), 'audience': ('受众匹配', 15),
    'performance': ('内容表现', 10), 'commercial': ('合作可行性', 5),
    'risk_quality': ('风险质量', 5),
}

def summarize(entry):
    entry = entry or {}
    unknown = set(entry) - set(DIMENSIONS)
    if unknown:
        raise ValueError(f'Unknown score dimensions: {unknown}')
    points, coverage = 0, 0
    rows = []
    for key, (label, weight) in DIMENSIONS.items():
        item = entry.get(key, {})
        rating = item.get('rating')
        reason = item.get('reason', '资料不足，待核；不记为零分。')
        if rating is not None:
            if isinstance(rating, bool) or not isinstance(rating, (int, float)) or not 0 <= rating <= 5:
                raise ValueError(f'Invalid rating: {key}={rating}')
            if not item.get('reason'):
                raise ValueError(f'Missing evidence for {key}')
            earned = round(rating / 5 * weight, 2)
            points += earned
            coverage += weight
        else:
            earned = None
        rows.append((label, weight, rating, earned, reason))
    content = None
    if all(entry.get(k, {}).get('rating') is not None for k in ('natural_seeding', 'brand_fit')):
        content = sum(r[3] for r in rows[:2])
    return {'total': round(points, 2) if coverage == 100 else None,
            'subtotal': round(points, 2), 'coverage': coverage,
            'content': content, 'rows': rows}
