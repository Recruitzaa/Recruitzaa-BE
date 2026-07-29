"""
shared/messaging/topics.py — All Kafka topic names as constants.
"""

# ── User Events ───────────────────────────────────────────
USER_REGISTERED = "user.registered"
USER_ROLE_CHANGED = "user.role.changed"
USER_ROLE_ADDED = "user.role.added"  # v3: second role granted

# ── Job Events ────────────────────────────────────────────
JOB_CREATED = "job.created"
JOB_APPROVED = "job.approved"
JOB_SCRAPED = "job.scraped"

# ── Application Events ────────────────────────────────────
APPLICATION_CREATED = "application.created"
APPLICATION_STAGE_MOVED = "application.stage.moved"

# ── Expert Events (v3) ────────────────────────────────────
EXPERT_SESSION_BOOKED = "expert.session.booked"
EXPERT_SESSION_COMPLETED = "expert.session.completed"

# ── Employee Events (v3) ──────────────────────────────────
EMPLOYEE_TIMESHEET_SUBMITTED = "employee.timesheet.submitted"

# ── AI Events ─────────────────────────────────────────────
AI_SCORE_REQUEST = "ai.score.request"
AI_SCORE_COMPLETED = "ai.score.completed"
AI_PARSE_REQUEST = "ai.parse.request"

# ── Notification Events ───────────────────────────────────
NOTIFICATION_EMAIL = "notification.email"
NOTIFICATION_PUSH = "notification.push"

# ── Analytics Events ──────────────────────────────────────
ANALYTICS_EVENT = "analytics.event"

# All topics (for admin tooling / topic creation)
ALL_TOPICS = [
    USER_REGISTERED,
    USER_ROLE_CHANGED,
    USER_ROLE_ADDED,
    JOB_CREATED,
    JOB_APPROVED,
    JOB_SCRAPED,
    APPLICATION_CREATED,
    APPLICATION_STAGE_MOVED,
    EXPERT_SESSION_BOOKED,
    EXPERT_SESSION_COMPLETED,
    EMPLOYEE_TIMESHEET_SUBMITTED,
    AI_SCORE_REQUEST,
    AI_SCORE_COMPLETED,
    AI_PARSE_REQUEST,
    NOTIFICATION_EMAIL,
    NOTIFICATION_PUSH,
    ANALYTICS_EVENT,
]
