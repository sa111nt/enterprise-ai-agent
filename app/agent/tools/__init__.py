from app.agent.tools.company_contacts import company_contacts
from app.agent.tools.department_info import department_info
from app.agent.tools.employee_lookup import employee_lookup
from app.agent.tools.onboarding_status import onboarding_status
from app.agent.tools.search_regulations import search_regulations

all_tools = [
    search_regulations,
    employee_lookup,
    onboarding_status,
    department_info,
    company_contacts,
]

PERSONAL_DATA_TOOLS = {"employee_lookup", "onboarding_status"}
