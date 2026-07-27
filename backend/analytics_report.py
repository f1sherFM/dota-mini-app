"""Pure formatting helpers for the admin /analytics command."""

ANALYTICS_EVENT_LABELS = {
    "bot_start":             "/start",
    "bot_help":              "/help",
    "bot_quiz_last":         "/last_quiz",
    "bot_quiz_hero":         "/hero_quiz",
    "bot_counters":          "/counters",
    "bot_synergy":           "/synergy",
    "bot_news":              "/news",
    "bot_feedback":          "/feedback",
    "page_home":             "Главная",
    "page_drafter":          "Драфтер",
    "page_quiz":             "Квизы",
    "page_database":         "База героев",
    "page_fantasy":          "Фэнтези",
    "page_profile":          "Профиль",
    "page_teammates":        "Пати",
    "page_teammate_review":  "Экран отзыва",
    "page_minigame_hl":      "Больше / Меньше",
    "page_donate":           "Поддержка",
    "page_feedback":         "Фидбек",
    "page_news":             "Новости",
    "page_hub_play":         "Хаб «Развлечения»",
    "page_hub_tools":        "Хаб «Инструменты»",
    "support_click":         "Поддержать — кликов",
    "page_draft_battle":     "Битва драфтов — открыт экран",
    "battle_queue":          "Битва — встал в очередь",
    "battle_start":          "Битва — началась",
    "battle_vs_bot":         "Битва — против бота",
    "battle_finish":         "Битва — доиграна",
    "battle_afk":            "Битва — AFK",
    "battle_forfeit":        "Битва — сдался",
}


def format_analytics_messages(analytics: dict, days: int) -> list[str]:
    daily = analytics.get("daily", [])
    total_dau = sum(day["dau"] for day in daily)
    total_new = sum(day["new"] for day in daily)
    avg_dau = round(total_dau / len(daily)) if daily else 0
    daily_lines = "\n".join(
        f"  • {day['day']} — DAU {day['dau']} "
        f"(нов: {day['new']} · верн: {day['returning']})"
        for day in daily
    ) or "  • —"

    features = analytics.get("features", [])
    feature_lines = "\n".join(
        f"  • {ANALYTICS_EVENT_LABELS.get(row['event'], row['event'])}: "
        f"{row['opens']} откр · {row['users']} юзеров · "
        f"{float(row.get('opens_per_user') or 0):.1f}/юз."
        for row in features
    ) or "  • —"

    funnel = analytics.get("battle_funnel") or {}
    funnel_lines = "\n".join(
        f"  • {ANALYTICS_EVENT_LABELS.get(step['event'], step['event'])}: "
        f"{step['opens']} событий · {step['users']} юзеров"
        for step in funnel.get("steps", [])
    ) or "  • —"

    def _pct(label: str, value) -> str:
        return f"  • {label}: —" if value is None else f"  • {label}: {value:g}%"

    funnel_rates = "\n".join((
        _pct("очередь → старт", funnel.get("queue_to_start_pct")),
        _pct("старт → финиш", funnel.get("start_to_finish_pct")),
        _pct("AFK от стартов", funnel.get("afk_per_start_pct")),
        _pct("сдались от стартов", funnel.get("forfeit_per_start_pct")),
    ))

    def _retention_line(label: str, retention: dict) -> str:
        pct = retention.get("avg_pct")
        cohorts = retention.get("cohorts", 0)
        if pct is None:
            return f"  • {label}: — (нет данных)"
        return f"  • {label}: {pct}% (по {cohorts} cohort'ам)"

    def _feature_metric(metric: dict) -> str:
        pct = metric.get("pct")
        if pct is None:
            return "—"
        return (
            f"{pct:g}% "
            f"({metric.get('retained', 0)}/{metric.get('users', 0)})"
        )

    feature_retention_lines = []
    for row in analytics.get("feature_retention", []):
        label = ANALYTICS_EVENT_LABELS.get(row["event"], row["event"])
        feature_retention_lines.append(
            f"  • {label}: D1 {_feature_metric(row.get('d1') or {})} · "
            f"D7 {_feature_metric(row.get('d7') or {})}"
        )
    feature_retention_text = "\n".join(feature_retention_lines) or "  • —"

    overview = (
        f"📊 Аналитика D2Helper (окно {days} дн.)\n\n"
        f"📅 По дням:\n{daily_lines}\n\n"
        f"📈 Итого за окно: новых {total_new} · средний DAU ≈ {avg_dau}\n\n"
        f"💖 Поддержать — кликов: {analytics.get('support_clicks', 0)}"
    )
    details = (
        f"🔧 Использование по фичам:\n{feature_lines}\n\n"
        f"⚔️ Воронка битвы:\n{funnel_lines}\n{funnel_rates}\n\n"
        f"♻️ Общий retention:\n"
        f"{_retention_line('D1', analytics.get('retention_d1') or {})}\n"
        f"{_retention_line('D7', analytics.get('retention_d7') or {})}\n\n"
        f"🧲 Retention по фичам первого дня:\n{feature_retention_text}\n"
        f"  ↳ Группы пересекаются: один пользователь может быть в нескольких строках."
    )
    return [overview, details]
