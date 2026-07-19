MONTH_TITLES = ['january', 'february', 'march', 'april', 'june', 'july', 'august', 'september', 'october', 'november',
                'december']

MEETING_MINUTES_TITLE_GREAT_KEYWORDS = ["meeting minutes", "meeting notes"]
MEETING_MINUTES_TITLE_KEYWORDS = ["sprint review", "retrospective", "omm", "standup", "monthly", "weekly", "meeting"]
MEETING_MINUTES_BODY_KEYWORDS = ["attendees", "presenter", "participants"]

WORKSHOP_MINUTES_TITLE_GREAT_KEYWORDS = ["5 why", "5why", "workshop"]
WORKSHOP_MINUTES_TITLE_KEYWORDS = ["sprint review", "retrospective", "retro", "ws", "standup", "butsam", "analysis"]
WORKSHOP_BODY_KEYWORDS = ["why 1", "why1", "why 2", "why2", "why 3", "why3", "why 4", "why4", "why 5", "why5",
                          "topic 1:", "topic 2:", "topic 3:", "topic 4:", "topic 5:"]

RELEASE_TITLE_KEYWORDS = ["release notes", "release", "deployment", "hotfix"]
RELEASE_BODY_KEYWORDS = ["approval", "approver", "deploy", "deployment", "mr", "merge request", "code freeze",
                        "pipeline", "bug", "regression", "hotfix", "patch", "version", "release", "execution",
                        "feature flag", "prod", "p", "qas", "qa", "uat"]
RELEASE_BODY_GREAT_KEYWORDS = ["zephyr"]
RELEASE_ANTI_KEYWORDS = ["meeting", "minutes", "retrospective", "5-why", "5 why", "agenda", "action item",
                        "attendance", "participants", "presenter"]

BUG_BODY_KEYWORDS = ["r1", "r2", "r3", "r4", "p1", "p2", "p3", "p4"]

PERFORMANCE_TITLE_KEYWORDS = ["performance", "report", "stress", "load", "test"]
PERFORMANCE_BODY_KEYWORDS = ["performance", "stress", "load", "throughput", "latency", "rps", "requests per second",
                        "benchmark", "scalability", "response time", "locust","loadrunner", "test", "report",
                        "rds", "api", "loaded", "loading", "grafana", "consumed"]
PERFORMANCE_ANTI_KEYWORDS = ["meeting", "minutes", "retrospective", "5-why", "5 why", "agenda", "action item",
                        "attendance", "participants", "presenter", "draft"]

LANDING_PAGE_TITLE_ANTI_KEYWORDS = ["onboarding", "plan", "retrospective", "test", "release"]

INTRO_PAGE_TITLE_KEYWORDS = ["intro", "hub"]
INTRO_PAGE_TITLE_ANTI_KEYWORDS = ["meeting", "minutes", "retrospective", "status", "review", "release", "deployment",
                            "hotfix", "onboarding"]

SOLUTION_DOC_TITLE_KEYWORDS = ["ddd", "add"]
SOLUTION_DOC_HEADER_KEYWORDS = ["solution", "diagram", "revision", "introduction",
                         "component", "microservice", "performance", "considerations",
                         "raid", "rollback", "references", "prerequisites", "pre-requisites", "high-level", "high level"]

TITLE_KEYWORD_LISTS = {
    "t_month": MONTH_TITLES,
    "t_g_meeting_minutes": MEETING_MINUTES_TITLE_GREAT_KEYWORDS,
    "t_meeting_minutes": MEETING_MINUTES_TITLE_KEYWORDS,
    "t_g_workshop_minutes": WORKSHOP_MINUTES_TITLE_GREAT_KEYWORDS,
    "t_workshop_minutes": WORKSHOP_MINUTES_TITLE_KEYWORDS,
    "t_release": RELEASE_TITLE_KEYWORDS,
    "t_performance": PERFORMANCE_TITLE_KEYWORDS,
    "t_anti_landing": LANDING_PAGE_TITLE_ANTI_KEYWORDS,
    "t_intro": INTRO_PAGE_TITLE_KEYWORDS,
    "t_anti_intro": INTRO_PAGE_TITLE_ANTI_KEYWORDS,
    "t_solution": SOLUTION_DOC_TITLE_KEYWORDS,
}

HEADERS_KEYWORD_LISTS = {
    "h_solution": SOLUTION_DOC_HEADER_KEYWORDS,
}

BODY_KEYWORD_LISTS = {
    "b_meeting_minutes": MEETING_MINUTES_BODY_KEYWORDS,
    "b_workshop": WORKSHOP_BODY_KEYWORDS,
    "b_g_release": RELEASE_BODY_GREAT_KEYWORDS,
    "b_release": RELEASE_BODY_KEYWORDS,
    "b_anti_release": RELEASE_ANTI_KEYWORDS,
    "b_performance": PERFORMANCE_BODY_KEYWORDS,
    "b_anti_performance": PERFORMANCE_ANTI_KEYWORDS,
    "b_bug": BUG_BODY_KEYWORDS,
}