"""
Demo accounts, shared by the seed script and the public welcome page.

All are @proofpath.demo, which seed/demo.py insists on, so nothing here can touch a Nirikshan account.
Every institution and person is fictional.
"""
DOMAIN = "@proofpath.demo"

INSTITUTIONS = [
    {"code": "INST-1001", "name": "Aarohan Institute of Technology", "city": "Pune"},
    {"code": "INST-1002", "name": "Vindhya College of Engineering", "city": "Nagpur"},
]

# email, full name, role, institution code, what the account is for
ACCOUNTS = [
    ("institution@proofpath.demo", "Aarohan Institute (applicant)", "institution", "INST-1001",
     "Prepares Aarohan's application: uploads documents and sees what each file check found."),
    ("reviewer@proofpath.demo", "Scrutiny reviewer", "reviewer", None,
     "Opens any application and its documents, at the exact page a value was read from."),
    ("ruleadmin@proofpath.demo", "Rule administrator", "rule_admin", None,
     "Looks after the illustrative rules, checklists and extraction templates."),
    ("institution2@proofpath.demo", "Vindhya College (applicant)", "institution", "INST-1002",
     "A second institution, to show that one institution never sees another's files."),
    ("ruleadmin2@proofpath.demo", "Second rule administrator", "rule_admin", None,
     "Approves rule changes written by the first, since nobody may approve their own."),
]
