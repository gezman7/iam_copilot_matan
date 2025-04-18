
MINIMAL_GUIDELINES = {
    "INACTIVE_USERS": (
        "Inactive user accounts that haven’t authenticated in over a defined period should be automatically "
        "flagged and reviewed monthly through system workflows to determine necessity. Organizations must establish "
        "threshold-based policies for inactivity, deactivating or restricting dormant accounts, conducting periodic "
        "audits, maintaining logs. This reduces risk of unauthorized access through orphaned credentials."
    ),
    "WEAK_MFA_USERS": (
        "To reduce exposure, Weak MFA implementations that rely on interceptable factors such as SMS pose elevated "
        "security risks. Organizations should enforce cryptographically resilient authenticators, require regular "
        "rotation of MFA credentials, disable deprecated methods, Training users on phishing threats, deploying "
        "hardware tokens or authenticator apps, periodic security reviews mitigate potential breaches."
    ),
    "SERVICE_ACCOUNTS": (
        "Service accounts require strict governance due to their elevated privileges. Organizations must enforce least "
        "privilege, implement credential rotation, restrict network scopes, audit usage. Monitoring should detect "
        "activity patterns or permission escalations. Segregating service account contexts, enabling just-in-time "
        "access, integrating with centralized identity systems reduces the risk of lateral movement compromise."
    ),
    "LOCAL_ACCOUNTS": (
        "Local accounts managed outside centralized directories introduce inconsistent security postures, gaps in auditing. "
        "Organizations should minimize local user creation, enforce strong password policies, integrate systems with "
        "enterprise identity providers. Regularly review and disable obsolete local credentials, implement multifactor "
        "authentication where possible, maintain comprehensive logs to detect unauthorized access privilege abuses."
    ),
    "NEVER_LOGGED_IN_USERS": (
        "Accounts provisioned but never authenticated increase attack surface by remaining undetected in audits. "
        "Organizations must implement automated detection for accounts with zero login events, review provisioning "
        "workflows to prevent orphan accounts, enforce time-bound validation requiring initial login within a defined "
        "window. Dormant unused accounts should be disabled or removed promptly."
    ),
    "NO_MFA_USERS": (
        "Absence of any multifactor authentication leaves accounts vulnerable to credential-based attacks. "
        "Organizations must mandate MFA enrollment at first login, configure authenticators with phishing-resistant "
        "methods, monitor enrollment compliance metrics, remediate non-compliant users. Implement progressive enforcement "
        "policies, provide user training to ensure universal adoption, thereby reducing the risk of unauthorized access."
    ),
    "PARTIALLY_OFFBOARDED_USERS": (
        "Accounts left active in some systems after employee departure can be exploited by insiders adversaries. "
        "Organizations should automate deprovisioning workflows across all applications, maintain synchronized user "
        "directories, conduct periodic reconciliation between HR records and system accounts, audit residual access. "
        "Immediate revocation of all credentials upon offboarding minimizes unauthorized access risks."
    ),
    "RECENTLY_JOINED_USERS": (
        "Newly onboarded users may receive excessive privileges before proper role assignments. Organizations should "
        "strictly enforce least-privilege provisioning, require manager approval for elevated access, implement a "
        "probationary period with automated activity monitoring, schedule early access reviews. Provide targeted "
        "security awareness training, adjust permissions based on observed behavior to mitigate onboarding risks."
    ),
}

# risk_summaries.py

GUIDELINES = {
    "Partially Offboarded Users": """
Partially offboarded users—accounts that remain active on some systems after an employee’s departure—pose a significant security risk. The guidance in NIST SP 800‑53 emphasizes comprehensive account management controls to ensure that once an employee leaves, all associated credentials are immediately revoked across every system. This process minimizes the likelihood of unintended access that could be exploited by malicious insiders or external attackers. Meanwhile, NIST SP 800‑171 reinforces the importance of well‑defined de‑provisioning procedures and periodic audits to detect any residual accounts. The documents collectively recommend automation of the offboarding process, cross‑referencing of user lists with system access, and rigorous logging of account removals. Together, these practices help prevent an environment in which orphaned or partially removed accounts could be leveraged to breach data security. Ultimately, establishing robust policies, coupled with continual verification and auditing, ensures all user privileges are consistently terminated at the right juncture, thereby closing potential security gaps and upholding the integrity of the organization’s identity management system.
""",
    "INACTIVE_USERS": """
Inactive user accounts—those that have not been accessed for prolonged periods—present an underappreciated risk within IAM frameworks. As outlined in NIST SP 800‑53, dormant accounts can be targeted by attackers seeking an entry point into an organization’s network. The publication advises regular reviews and automated deactivation policies to mitigate risks related to lack of activity. NIST SP 800‑171 further explains that inactive accounts might bypass routine monitoring, thus requiring targeted controls to ensure they do not become exploited access points for unauthorized parties. The guidelines suggest establishing time‑bound criteria for inactivity and subsequent account suspension or removal. Additionally, routine auditing of logs and correlation of user activity across systems is recommended to identify anomalies associated with dormant accounts. Combining process automation with clear policies enables organizations to address the potential threat vectors. In essence, this dual guidance underscores that inactive accounts must be systematically managed and de‑provisioned to enhance overall security posture and reduce the risk of compromised credentials, thereby maintaining a secure and compliant environment.
""",
    "NEVER_LOGGED_IN_USERS ": """
Accounts that have never been used despite being provisioned—“never logged in” users—can indicate both operational oversights and latent security vulnerabilities. NIST SP 800‑53 stresses that every account provisioned must be validated through use to confirm proper identity verification. Unused accounts may result from erroneous provisioning or a failure in workflow handover, leaving open doors that adversaries might exploit. NIST SP 800‑171 builds on this concept by recommending a periodic review of all provisioned accounts. It emphasizes that dormant, unused accounts should be disabled or deleted if no longer required. The risk here is twofold: such accounts may be neglected in system audits and become an attractive target for attackers looking to bypass multi‑layered security. Both publications advocate for automated detection tools to flag accounts that have never seen login activity and stress the need for robust onboarding protocols. By ensuring that every account is either actively managed or appropriately decommissioned, organizations can reduce their attack surface. This dual approach—verification upon creation and timely removal when unused—helps maintain strict control over all active accounts.
""",
    "NO_MFA_USERS": """
The absence of strong multi‑factor authentication (MFA) significantly heightens the risk of unauthorized access. NIST SP 800‑63B clearly outlines the requirements for robust digital authentication, emphasizing that MFA should combine multiple independent factors to ensure the highest assurance levels. When MFA is either not enabled or implemented with weak methods (such as SMS‑based tokens that can be intercepted), accounts are left vulnerable to phishing and credential compromise. Complementing this, NIST SP 800‑53 stresses that organizations must implement technical safeguards that enforce strong authentication and regularly assess the effectiveness of these controls. Weak MFA can undermine an organization’s layered defense strategy, leaving it susceptible to sophisticated attacks that bypass single‑factor methods. The guidance insists on a continual review of authenticators and the adoption of resilient methods like hardware tokens or biometric factors. Both documents advocate for detailed risk assessments to validate that all access points are protected by MFA standards capable of resisting modern threats. Enforcing strict MFA policies and ensuring proper technical configuration can dramatically reduce the potential for breaches, thereby protecting sensitive data and critical systems.
""",
    "SERVICE_ACCOUNTS": """
Service accounts—non‑human accounts used by applications and automated services—demand specialized risk management measures due to their unique role and elevated privileges. NIST SP 800‑53 advises that these accounts be treated differently from standard user accounts by enforcing strict control mechanisms and continuous monitoring. Service accounts often have broader access rights and, if not tightly controlled, can be exploited to move laterally across systems. NIST SP 800‑171 further underlines the critical need to segregate service account credentials from those of regular users and to limit their permissions strictly to operational necessities. Both documents recommend rigorous account lifecycle management, including periodic reviews and use of automated tools to detect unauthorized changes. These publications stress that misconfigured service accounts create persistent vulnerabilities that may bypass routine security defenses, making them a common target for attackers seeking to escalate privileges. The guidelines underscore the importance of documenting service account usage, hardening authentication techniques, and employing continuous logging and audit practices to promptly identify and mitigate any anomalies. This tailored approach ensures that service accounts do not become the weak link in an organization’s overall security framework.
""",
    "LOCAL_ACCOUNTS": """
Local accounts—those managed on a single system without centralized oversight—present distinct challenges in identity management. According to NIST SP 800‑53, centralized control of account credentials is crucial for ensuring consistent security policies. Local accounts, when unmanaged, can lead to disparate security postures across an organization’s systems. NIST SP 800‑171 adds that such accounts are particularly vulnerable to misconfiguration and lack the benefit of enterprise‑level monitoring. This decentralization complicates auditing processes and can result in outdated or excessive permissions remaining active far longer than necessary. Both documents advocate for the adoption of centralized identity providers or directories, which help standardize access controls and simplify the de‑provisioning process. Regular audits are essential to identify local accounts that do not meet current policy requirements, and organizations are advised to disable unnecessary accounts promptly. The recommended safeguards include using automated tracking tools and strict access recertification cycles. By managing local accounts centrally and ensuring periodic review, organizations can significantly reduce the likelihood of exploitation via outdated or unmanaged credentials, thus strengthening their overall security posture.
""",
    "RECENTLY_JOINED_USERS": """
Newly onboarded users represent a unique security challenge as they transition into full integration within an organization’s IT environment. NIST SP 800‑53 highlights that new accounts must be provisioned in strict accordance with role‑based access control policies, ensuring that only the minimum necessary privileges are granted at the outset. The guidelines recommend enhanced monitoring during the initial period to detect any unusual behavior or misconfigurations. In parallel, NIST SP 800‑171 emphasizes the importance of secure onboarding processes that incorporate immediate identity verification and training on security best practices. Recently joined users may inadvertently expose vulnerabilities due to incomplete familiarity with security protocols or over‑provisioned access rights. Both documents stress the need for continuous access recertification and real‑time adjustments as users transition from probationary statuses to full privileges. By employing automated tools for tracking user behavior and timely review of access permissions, organizations can quickly identify and mitigate any anomalous access patterns. This dual framework not only fortifies the overall identity management lifecycle but also minimizes the risks associated with the early stages of user integration, ensuring sustained adherence to security best practices.
"""
}


# guidelines.py

GENERAL_GUIDELINE = """
Identity and Access Management (IAM) frameworks are critical for safeguarding organizational resources but present multifaceted risks when not managed holistically. Central to these risks are improper user lifecycle controls: orphaned accounts left active due to incomplete offboarding, dormant accounts from inactive or never-logged-in users, and newly onboarded individuals granted excessive privileges before proper vetting. Authentication weaknesses—such as absent or easily compromised multi-factor authentication (MFA) methods—further degrade security posture by enabling credential-based attacks. Elevated-privilege entities, including service accounts and locally managed accounts, exacerbate threats when they bypass centralized governance, evade comprehensive auditing, or retain unnecessary permissions. Effective mitigation demands automated, policy-driven workflows encompassing secure provisioning, role-based least-privilege enforcement, robust MFA mandates, and timely deprovisioning across all platforms. Continuous monitoring, anomaly detection, and periodic audits synchronized with authoritative identity directories ensure swift identification and remediation of residual credentials and anomalous activities. Organizations must also enforce probationary monitoring for new users, implement regular credential rotation for service accounts, and eliminate redundant local accounts through integration with centralized identity providers. Coupled with targeted security training and adherence to industry standards—such as NIST guidelines—this holistic strategy reduces attack surface, ensures regulatory compliance, and preserves the integrity and resilience of enterprise IAM ecosystems against evolving identity-based threats.
"""

MINIMAL_GENERAL_GUIDELINE = """
IAM risk spans the entire user lifecycle: from over-provisioned new hires and orphaned or dormant accounts to service and local accounts circumventing centralized controls, and weak or absent MFA. Mitigation requires automated provisioning and deprovisioning, least-privilege enforcement, robust MFA, continuous monitoring, and periodic audits and compliance checks aligned with standards.
"""
