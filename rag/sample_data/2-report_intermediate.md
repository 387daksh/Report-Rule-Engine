# Document Transcript: 2-report.pdf

*Extracted Pages: 29 | Detected Tables: 18 | Total Chars: 33131*

<!-- PAGE_START: 1 -->
## Page 1

### Table 1.1
| Report Release Date | 29/05/2026 |
| --- | --- |
| Type of Audit | API Security Testing Report |
| Type of Audit Report | Initial Audit Report |
| Period | 07/04/2026 to 10/04/2026 |

### Table 1.2
|  |  |  | Document Preparation |
| --- | --- | --- | --- |
| Document Title | Document Title |  | Tatva API Security Testing Report |
| Document ID |  |  | NA |
| Document Version |  |  | 1.0 |
| Prepared by |  |  | Chandar. A |
| Reviewed by |  |  | Nikhil |
| Approved by |  |  | Paul |
| Released by |  |  | Kumar |
| Release date |  |  | 29/05/2026 |

### Page Text Content
RASVT 
API Assessment Security Testing Report  
           
Report Release Date  
29/05/2026  
Type of Audit  
API Security Testing Report  
Type of Audit Report  
Initial Audit Report  
Period  
07/04/2026 to 10/04/2026  
Document Control  
 
Document Preparation   
Document Title    
Tatva API Security Testing Report  
Document ID    
NA  
Document Version    
1.0  
Prepared by    
Chandar. A  
Reviewed by    
Nikhil  
Approved by    
Paul  
Released by    
Kumar  
Release date    
29/05/2026

<!-- PAGE_END: 1 -->
---

<!-- PAGE_START: 2 -->
## Page 2

### Table 2.1
|  |  |  | Document Change History |  |  |  |
| --- | --- | --- | --- | --- | --- | --- |
| 1.0 |  |  | 29/05/2026 | Initial Audit Report |  |  |

### Table 2.2
|  |  |  | Document Distribution List |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Name | Name |  | Organization | Designation | Email Id | Email Id |  |
| Pulkit Madhusudan Puri |  |  | RASVT | Deputy General Manager | pulkit.puri@VERAH.com |  |  |
| Ramanjaneya Reddy |  |  | RASVT | Staff Engineering Manager | cr.reddy@VERAH.com |  |  |

### Page Text Content
Document Change History   
 
1.0  
29/05/2026  
Initial Audit Report  
  
 
Document Distribution List   
 
Name    
Organization    
Designation    
Email Id    
Pulkit Madhusudan Puri  
RASVT 
Deputy General Manager  
pulkit.puri@VERAH.com  
Ramanjaneya Reddy  
RASVT 
Staff Engineering Manager  
cr.reddy@VERAH.com  
    
  
Contents   
Introduction 
3 
Engagement Scope 
3 
Details of Auditing Team 
6 
Audit Activities and Timelines 
6 
Audit Methodology and Criteria/Standard Referred 
6 
Tools/Software Used 
7 
Executive Summary 
9 
Detailed Observations 
12 
Appendices 
28

<!-- PAGE_END: 2 -->
---

<!-- PAGE_START: 3 -->
## Page 3

### Table 3.1
|  | Sr. |  | API Endpoints |
| --- | --- | --- | --- |
|  | No. |  |  |
| 1 |  |  | https://in-Tatva-tr.stg.VERAHpay.ca/pf/v1/enrollments |
| 2 |  |  | https://in-Tatva-tr.stg.VERAHpay.ca/pf/v1/enrollments/ |

### Page Text Content
Introduction  
Project Background:   
Tatva was engaged to perform API Assessment for VERAH. This assessment utilized tools and techniques analogous to those employed by malicious 
attackers, focusing on evaluating the security of VERAH’s API infrastructure in terms of confidentiality, integrity, and availability. The primary objective 
was to uncover both technical and logical vulnerabilities within APIs and to provide strategic recommendations for mitigating risks that could arise 
from these vulnerabilities.  
Objective:  
Conduct comprehensive API assessment to identify and assess vulnerabilities in API’s, thereby enhancing VERAH’s security posture and effectively 
protecting against external threats.  
Assumptions:   
Based on the scope, only the specified APIs were tested. This report has been produced based on the test that was conducted on a particular date 
tested. Vulnerability details provided in this report are based on the API’s provided for assessment considering test was performed on a production 
or identical to production environment.  
It is recommended that prior to acting on the recommendations, following actions are assumed to be taken by VERAH:  
• 
Any vulnerabilities identified after the assessment date may also not form part of this report.  
• 
GT provided the reference link in the detailed vulnerability section for VERAH reference only.   
• 
Any fix to application/system should be tested on UAT or non-production environment prior to any patch deployment on production 
environment.   
• 
Appropriate backup and rollback plan are made prior to implementing the recommendation on the system.  
• 
This report is intended solely for the information and internal use of VERAH.  
• 
VERAH’s team is responsible for applying security fixes and maintaining effective security controls on application, network, and system.  
Engagement Scope  
Below details of assets covered in the scope are included in this section along with other relevant details.  
Sr. 
No.  
API Endpoints  
1  
https://in-Tatva-tr.stg.VERAHpay.ca/pf/v1/enrollments  
 
2  
https://in-Tatva-tr.stg.VERAHpay.ca/pf/v1/enrollments/

<!-- PAGE_END: 3 -->
---

<!-- PAGE_START: 4 -->
## Page 4

### Table 4.1
| 3 | https://in-Tatva-tr.stg.VERAHpay.ca/pf/v1/tokens |
| --- | --- |
| 4 | https://in-Tatva-tr.stg.VERAHpay.ca/pf/v1/resource/ |
| 5 | https://in-Tatva-tr.stg.VERAHpay.ca/pf/v1/reports |
| 6 | https://in-Tatva-tr.stg.VERAHpay.ca/pf/v1/tokens/select-activation |
| 7 | https://in-Tatva-tr.stg.VERAHpay.ca/pf/v1/tokens/ |
| 8 | https://in-Tatva-tr.stg.VERAHpay.ca/ws/v1/tokens?user.id= |
| 9 | https://in-Tatva-tr.stg.VERAHpay.ca/ws/v1/tokens/ |
| 10 | https://in-Tatva-tr.stg.VERAHpay.ca/ws/v1/tokens?user.id=&wallet.id= |
| 11 | https://in-Tatva-tr.stg.VERAHpay.ca/ws/v1/tokens?wallet.id= |
| 12 | https://in-Tatva-tr.stg.VERAHpay.ca/ws/v1/tokens/?wallet.id= |
| 13 | https://in-Tatva-tr.stg.VERAHpay.ca/ts/v1/notifications/tokenStatusChangeNotification |
| 14 | https://in-Tatva-tr.stg.VERAHpay.ca/ts/v1/notifications/replenishNotification |
| 15 | https://in-Tatva-tr.stg.VERAHpay.ca/ts/v1/notifications/transactionNotification |

### Page Text Content
3  
https://in-Tatva-tr.stg.VERAHpay.ca/pf/v1/tokens  
4  
https://in-Tatva-tr.stg.VERAHpay.ca/pf/v1/resource/  
5  
https://in-Tatva-tr.stg.VERAHpay.ca/pf/v1/reports  
6  
https://in-Tatva-tr.stg.VERAHpay.ca/pf/v1/tokens/select-activation  
7  
https://in-Tatva-tr.stg.VERAHpay.ca/pf/v1/tokens/  
8  
https://in-Tatva-tr.stg.VERAHpay.ca/ws/v1/tokens?user.id=  
9  
https://in-Tatva-tr.stg.VERAHpay.ca/ws/v1/tokens/  
10  
https://in-Tatva-tr.stg.VERAHpay.ca/ws/v1/tokens?user.id=&wallet.id=  
11  
https://in-Tatva-tr.stg.VERAHpay.ca/ws/v1/tokens?wallet.id=  
12  
https://in-Tatva-tr.stg.VERAHpay.ca/ws/v1/tokens/?wallet.id=  
13  
https://in-Tatva-tr.stg.VERAHpay.ca/ts/v1/notifications/tokenStatusChangeNotification  
14  
https://in-Tatva-tr.stg.VERAHpay.ca/ts/v1/notifications/replenishNotification  
15  
https://in-Tatva-tr.stg.VERAHpay.ca/ts/v1/notifications/transactionNotification

<!-- PAGE_END: 4 -->
---

<!-- PAGE_START: 5 -->
## Page 5

### Table 5.1
| 16 | https://in-Tatva-tr.stg.VERAHpay.ca/pf/v1/tokens/{tokenid}/transactions?since= |
| --- | --- |

### Page Text Content
16  
https://in-Tatva-tr.stg.VERAHpay.ca/pf/v1/tokens/{tokenid}/transactions?since=  
  
Date up to which the list has been updated: 01/06/2026.

<!-- PAGE_END: 5 -->
---

<!-- PAGE_START: 6 -->
## Page 6

### Table 6.1
| Sr. No. | Name | Designation | Email Id | Professional Qualifications /Certifications |  | Whether the resource has |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  | been listed in the |
|  |  |  |  |  |  | Snapshot information |
|  |  |  |  |  |  | published on CERT-In’s |
|  |  |  |  |  |  | website (Yes/No) |
| 1 | Paul | Manager | Anubhav.paul@tat.com | CEH, eJPT | Yes |  |
| 2 | Nikhil | Manager | Nikhil.kumar@tat.com | CPTE, CEH, CHFI, CISEH, ISO 27001 | No |  |
| 3 | Chandra. A | Consultant | Chandrashekar.a@tat.com | CEH | No |  |

### Table 6.2
| Professional |
| --- |
| Qualifications |
| /Certifications |

### Table 6.3
| Sr. |
| --- |
| No. |

### Table 6.4
| Assessment Start Date | Assessment End Date |
| --- | --- |

### Page Text Content
Details of Auditing Team  
  
Sr. 
No.  
Name  
Designation  
Email Id  
Professional  
Qualifications  
/Certifications  
Whether the resource has 
been listed in the  
Snapshot information 
published on CERT-In’s 
website (Yes/No)  
1  
Paul  
Manager  
Anubhav.paul@tat.com 
CEH, eJPT  
Yes  
2  
Nikhil  
Manager  
Nikhil.kumar@tat.com 
CPTE, CEH, CHFI, CISEH, 
ISO 27001  
No  
3  
Chandra. A  
Consultant  
Chandrashekar.a@tat.com 
CEH  
No  
   
Audit Activities and Timelines  
Security Assessment timeline as follows:  
Assessment Start Date  
Assessment End Date  
07th April 2026  
10th April 2026  
   
  
  
Audit Methodology and Criteria/Standard Referred  
The API security assessment was conducted as an exercise. This was done to simulate as closely as possible the viewpoint of a completely external 
attacker. The following approach is followed performing the assessment on the API provided for testing.

<!-- PAGE_END: 6 -->
---

<!-- PAGE_START: 7 -->
## Page 7

### Embedded Visual Elements
[IMAGE_PAGE_7_FIG_1] *(Figure 1: page_7_fig_1.jpeg, 1600x900px)*

### Table 7.1
| S. No | Name of Tool/Software used | Version of the Tool/Software used | Open Source/Licensed |
| --- | --- | --- | --- |
| 1 | Postman | 12.9.0 | Licensed |

### Page Text Content
Tools/Software Used  
S. No  
Name of Tool/Software used  
Version of the Tool/Software used  
Open Source/Licensed  
1  
Postman  
12.9.0  
Licensed

<!-- PAGE_END: 7 -->
---

<!-- PAGE_START: 8 -->
## Page 8

### Table 8.1
| 2 | Burp Suite Professional | 2026.4.1 | Licensed |
| --- | --- | --- | --- |

### Page Text Content
2  
Burp Suite Professional  
2026.4.1  
Licensed

<!-- PAGE_END: 8 -->
---

<!-- PAGE_START: 9 -->
## Page 9

### Table 9.1
| 1 | https://in-Tatva- tr.stg.VERAHpay.ca/ws/vl/toke ns?user.id=LNPzjk6bRnWj5wJ KeOhExw https://in-Tatva- tr.stg.VERAHpay.ca/ws/vl/toke ns/1P031829bc33a3004a9eb7d acda511eb0ff8 https://in-Tatva- tr.stg.VERAHpay.ca/pf/vl/toke ns/1P033d6e0147084346b6a08 5814b9eb5d2f0/transactions?si nce=1775743985433 | Broken Access Control |  |  | CWE-284: Improper Access Control | High | It is recommended to: Enforce authentication checks across all API endpoints to ensure only legitimate users can access them. Implement strict authorization controls for sensitive operations such as token management to restrict access based on user roles and privileges. Apply object- level access control to ensure users can only interact with their own data. Ensure sensitive information is only returned after proper authentication validation. | NA | New |  |  | Open |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### Page Text Content
Executive Summary  
A high-level overview of the key audit findings and vulnerabilities. This section is for senior management to understand business risks.   
 
 
 
 
 
 
 
 
 
1  
https://in-Tatva- 
tr.stg.VERAHpay.ca/ws/vl/toke 
ns?user.id=LNPzjk6bRnWj5wJ 
KeOhExw  
  
https://in-Tatva- 
tr.stg.VERAHpay.ca/ws/vl/toke 
ns/1P031829bc33a3004a9eb7d 
acda511eb0ff8  
  
https://in-Tatva- 
tr.stg.VERAHpay.ca/pf/vl/toke 
ns/1P033d6e0147084346b6a08 
5814b9eb5d2f0/transactions?si 
nce=1775743985433  
Broken Access 
Control  
CWE-284:  
Improper  
Access 
Control  
High  
It is recommended to: Enforce 
authentication checks across  
all API endpoints to ensure 
only legitimate users can  
access them. Implement strict 
authorization controls for  
sensitive operations such as  
token management to restrict 
access based on user roles  
and privileges. Apply object- 
level access control to ensure  
users can only interact with 
their own data. Ensure  
sensitive information is only 
returned after proper 
authentication validation.  
NA  
New  
Open

<!-- PAGE_END: 9 -->
---

<!-- PAGE_START: 10 -->
## Page 10

### Table 10.1
| 2 | https://in-Tatva- tr.stg.VERAHpay.ca/pf/vl/toke ns | No Rate Limiting | CWE-307: Improper Restriction of Excessive Authenticati on Attempts | Medium | It is recommended to implement proper rate limiting and request throttling on the API endpoint, such as restricting the number of OTP attempts per user or IP address, introducing temporary lockouts after multiple failed attempts, and enforcing time-based cooldowns to prevent bruteforce and abuse scenarios. | NA | New | Open |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | https://in-Tatva- tr.stg.VERAHpay.ca/pf/vl/toke ns | OTP Misconfiguration | CWE-287: Improper Authenticati on | Medium | It is recommended to validate the OTP supplied in the Authorization header by matching it against a generated OTP tied to the user or request, enforcing expiration and rejecting invalid or reused values. | NA | New | Open |
| 4 | https://in-Tatva- tr.stg.VERAHpay.ca/pf/vl/enrol lments/ | Sensitive Information Disclosure | CWE-200: Exposure of Sensitive Information to an Unauthoriz ed Actor | Medium | It is recommended to restrict API responses to authorized and valid requests only by enforcing strict header validation, validating server identifiers, and ensuring sensitive certificates or internal configuration data are never exposed in API responses. | NA | New | Open |
| 5 | https://in-Tatva- tr.stg.VERAHpay.ca/pf/vl/reso urce/* | Insecure Direct Object Reference | CWE-639: Authorizatio n Bypass Through User- Controlled Key | Medium | It is recommended to: Implement strict server-side authorization checks to ensure that MID and DMID values are properly mapped to the authenticated user session. Validate that users can only access resources explicitly | NA | New | Open |

### Page Text Content
2  
https://in-Tatva- 
tr.stg.VERAHpay.ca/pf/vl/toke 
ns  
No Rate Limiting  
CWE-307:  
Improper  
Restriction 
of  
Excessive  
Authenticati 
on  
Attempts  
Medium  
It is recommended to 
implement proper rate limiting  
and request throttling on the  
API endpoint, such as 
restricting the number of OTP 
attempts per user or IP 
address, introducing  
temporary lockouts after  
multiple failed attempts, and 
enforcing time-based  
cooldowns to prevent 
bruteforce and abuse 
scenarios.  
NA  
New  
Open  
3  
https://in-Tatva- 
tr.stg.VERAHpay.ca/pf/vl/toke 
ns  
OTP  
Misconfiguration  
CWE-287: 
Improper  
Authenticati 
on  
Medium  
It is recommended to validate 
the OTP supplied in the  
Authorization header by 
matching it against a  
generated OTP tied to the  
user or request, enforcing  
expiration and rejecting invalid 
or reused values.  
NA  
New  
Open  
4  
https://in-Tatva- 
tr.stg.VERAHpay.ca/pf/vl/enrol 
lments/  
Sensitive  
Information  
Disclosure  
CWE-200:  
Exposure of 
Sensitive  
Information 
to an  
Unauthoriz 
ed Actor  
Medium  
It is recommended to restrict  
API responses to authorized 
and valid requests only by 
enforcing strict header  
validation, validating server  
identifiers, and ensuring  
sensitive certificates or  
internal configuration data are 
never exposed in API 
responses.  
NA  
New  
Open  
5  
https://in-Tatva- 
tr.stg.VERAHpay.ca/pf/vl/reso 
urce/*  
Insecure Direct  
Object  
Reference  
CWE-639:  
Authorizatio 
n Bypass  
Through  
User- 
Controlled  
Key  
Medium  
It is recommended to:  
Implement strict server-side 
authorization checks to ensure  
that MID and DMID values are 
properly mapped to the  
authenticated user session.  
Validate that users can only 
access resources explicitly  
NA  
New  
Open

<!-- PAGE_END: 10 -->
---

<!-- PAGE_START: 11 -->
## Page 11

### Table 11.1
|  |  |  |  |  | assigned to them. Avoid relying solely on client- |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  | supplied identifiers for access control. Use indirect references or token-based validation to securely fetch card details. |  |  |  |
| 6 | https://in- Tatvatr.stg.VERAHpay.ca/* | Improper Error Handling | CWE-209: Information Exposure Through an Error Message CWE-200: Exposure of Sensitive Information to an Unauthoriz ed Actor | Low | It is recommended to implement proper error handling by returning generic and user-friendly error messages for all API responses, while logging detailed error information securely on the server side, and ensuring that exception stack traces, database details, and internal system information are never exposed to end users. | NA | New | Open |
| 7 | https://in- Tatvatr.stg.VERAHpay.ca/* | Banner Grabbing | CWE-209: Information Exposure Through an Error Message CWE-200: Exposure of Sensitive Information | Low | It is recommended to configure the application and web server to suppress detailed error messages and remove server name and version information from all responses, including error pages, by using generic error messages instead. | NA | New | Open |

### Page Text Content
assigned to them. Avoid relying 
solely on client- 
 
 
 
 
 
supplied identifiers for access 
control. Use indirect  
references or token-based  
validation to securely fetch 
card details.  
 
 
 
6  
https://in-
Tatvatr.stg.VERAHpay.ca/*  
Improper Error 
Handling  
CWE-209:  
Information 
Exposure  
Through an  
Error 
Message 
CWE-200:  
Exposure of 
Sensitive  
Information 
to an  
Unauthoriz 
ed Actor  
Low  
It is recommended to 
implement proper error  
handling by returning generic 
and user-friendly error 
messages for all API  
responses, while logging  
detailed error information  
securely on the server side, 
and ensuring that exception  
stack traces, database details, 
and internal system  
information are never exposed 
to end users.  
NA  
New  
Open  
7  
https://in-
Tatvatr.stg.VERAHpay.ca/*  
Banner Grabbing 
CWE-209:  
Information 
Exposure  
Through an  
Error 
Message 
CWE-200:  
Exposure of 
Sensitive  
Information  
Low  
It is recommended to configure 
the application and web server 
to suppress  
detailed error messages and 
remove server name and  
version information from all 
responses, including error  
pages, by using generic error 
messages instead.  
NA  
New  
Open

<!-- PAGE_END: 11 -->
---

<!-- PAGE_START: 12 -->
## Page 12

### Page Text Content
Detailed Observations   
The details of identified vulnerabilities, impact, severity, and recommendations for the same are explained below  
1. Broken Access Control  
Status: Open  
Severity: High  
Detailed Observation:   
It was observed that the PATCH token management API and the user details API do not implement authentication or authorization checks. The 
endpoints allow token state modifications such as suspend and activate, and also return sensitive user information including token status and 
card URI details, without any authentication checks.  
Impact:  
An attacker can exploit these API endpoints to perform unauthorized token state changes and access sensitive user data. This may lead to 
exposure of confidential information, unauthorized account modifications, and potential misuse of sensitive resources, resulting in security and 
privacy risks.  
CVE/CWE:  
CWE-284: Improper Access Control  
Affected Asset:   
• 
https://in-Tatva-tr.stg.VERAHpay.ca/ws/vl/tokens?user.id=LNPzj  
• 
https://in-Tatva-tr.stg.VERAHpay.ca/ws/vl/tokens/1P031829bc33a3004a9eb7  
• 
https://in-Tatva-tr.stg.VERAHpay.ca/pf/vl/tokens/1P033d6e0147084346b6a085814 
• 
 
• 
Recommendation:   
  
It is recommended to:   
  
• 
Enforce authentication checks across all API endpoints to ensure only legitimate users can access them.  
• 
Implement strict authorization controls for sensitive operations such as token management to restrict access based on user roles and 
privileges. Apply object-level access control to ensure users can only interact with their own data. Ensure sensitive information is only 
returned after proper authentication validation.

<!-- PAGE_END: 12 -->
---

<!-- PAGE_START: 13 -->
## Page 13

### Embedded Visual Elements
[IMAGE_PAGE_13_FIG_1] *(Figure 1: page_13_fig_1.jpeg, 1307x489px)*

### Page Text Content
Reference: NA  
New or Repeat observation: New  
  
Proof of Concept:  
  
Scenario 1

<!-- PAGE_END: 13 -->
---

<!-- PAGE_START: 14 -->
## Page 14

### Embedded Visual Elements
[IMAGE_PAGE_14_FIG_1] *(Figure 1: page_14_fig_1.jpeg, 1306x486px)*

[IMAGE_PAGE_14_FIG_2] *(Figure 2: page_14_fig_2.jpeg, 1303x488px)*

<!-- PAGE_END: 14 -->
---

<!-- PAGE_START: 15 -->
## Page 15

### Embedded Visual Elements
[IMAGE_PAGE_15_FIG_1] *(Figure 1: page_15_fig_1.jpeg, 1299x500px)*

[IMAGE_PAGE_15_FIG_2] *(Figure 2: page_15_fig_2.jpeg, 1301x486px)*

### Page Text Content
Scenario 2  
 
 
Scenario 3

<!-- PAGE_END: 15 -->
---

<!-- PAGE_START: 16 -->
## Page 16

### Embedded Visual Elements
[IMAGE_PAGE_16_FIG_1] *(Figure 1: page_16_fig_1.jpeg, 1300x445px)*

### Page Text Content
2. No Rate Limiting  
Status: Open Severity: 
Medium  
Detailed Observation:   
It was observed that the API endpoint protected by an authorization header requiring a one-time password (OTP) does not enforce any rate 
limiting, allowing an attacker to continuously send a high number of requests without any restriction, delay, or blocking mechanism.  
Impact:  
A malicious actor can repeatedly send unauthorized or automated requests to brute-force OTP values or flood the endpoint, increasing the risk 
of unauthorized access, abuse of authentication mechanisms, and potential service degradation or denial of service for legitimate users.  
CVE/CWE:  
CWE-307: Improper Restriction of Excessive Authentication Attempt  
Affected Asset:   
• 
https://in-Tatva-tr.stg.VERAHpay.ca/pf/vl/tokens  
Recommendation:

<!-- PAGE_END: 16 -->
---

<!-- PAGE_START: 17 -->
## Page 17

### Embedded Visual Elements
[IMAGE_PAGE_17_FIG_1] *(Figure 1: page_17_fig_1.jpeg, 1299x451px)*

### Page Text Content
It is recommended to:   
  
• 
Implement proper rate limiting and request throttling on the API endpoint, such as restricting the number of OTP attempts per user or IP 
address,   
• 
Introduce temporary lockouts after multiple failed attempts, and enforcing time-based cooldowns to prevent brute-force and abuse 
scenarios.  
  
Reference: NA  
  
New or Repeat observation: New  
  
Proof of Concept:

<!-- PAGE_END: 17 -->
---

<!-- PAGE_START: 18 -->
## Page 18

### Page Text Content
3. OTP Misconfiguration  
Status: Open Severity: 
Medium  
Detailed Observation:   
It was observed that the application accepts an OTP value through the Authorization header but does not perform any validation of this value, 
allowing any arbitrary OTP to be treated as valid for authorization.  
Impact:  
A malicious actor can supply any random OTP in the Authorization header to bypass authentication controls and gain unauthorized access to 
protected endpoints and functionality.  
CVE/CWE:  
CWE‑287: Improper Authentication  
Affected Asset:   
 
•  
https://in-Tatva-tr.stg.VERAHpay.ca/pf/vl/tokens  
Recommendation:   
  
It is recommended to validate the OTP supplied in the Authorization header by matching it against a generated OTP tied to the user or request, 
enforcing expiration and rejecting invalid or reused values.  
Reference: NA  
New or Repeat observation: New  
  
  
  
Proof of Concept:

<!-- PAGE_END: 18 -->
---

<!-- PAGE_START: 19 -->
## Page 19

### Embedded Visual Elements
[IMAGE_PAGE_19_FIG_1] *(Figure 1: page_19_fig_1.jpeg, 1301x492px)*

<!-- PAGE_END: 19 -->
---

<!-- PAGE_START: 20 -->
## Page 20

### Page Text Content
4. Sensitive Information Disclosure  
Status: Open Severity: 
Medium  
Detailed Observation:   
It was observed that an API responds with sensitive certificate data, including NPCI certificates and device root certificates, when all security 
headers are removed and the server ID parameter is tampered with, indicating that access controls and response filtering are not properly 
enforced.  
Impact:  
A malicious actor can extract internal certificate information by manipulating request headers or parameters, which may aid in further attacks 
such as environment fingerprinting, trust chain analysis, or crafting more targeted exploitation attempts.  
CVE/CWE:  
CWE‑200: Exposure of Sensitive Information to an Unauthorized Actor  
Affected Asset:   
 
•  
https://in-Tatva-tr.stg.VERAHpay.ca/pf/vl/enrollments/  
Recommendation:   
  
It is recommended to restrict API responses to authorized and valid requests only by enforcing strict header validation, validating server 
identifiers, and ensuring sensitive certificates or internal configuration data are never exposed in API responses.  
Reference: NA  
New or Repeat observation: New  
  
  
  
Proof of Concept:

<!-- PAGE_END: 20 -->
---

<!-- PAGE_START: 21 -->
## Page 21

### Embedded Visual Elements
[IMAGE_PAGE_21_FIG_1] *(Figure 1: page_21_fig_1.jpeg, 1305x486px)*

[IMAGE_PAGE_21_FIG_2] *(Figure 2: page_21_fig_2.jpeg, 1305x492px)*

### Page Text Content
5. Insecure Direct Object Reference  
Status: Open Severity: 
Medium  
Detailed Observation:   
It was observed that the application allows access to card details by using MID and DMID parameters that differ for each device. However, by 
modifying the MID and DMID values to those of other devices, the user was still able to access card details within the same session, indicating 
improper authorization checks on these parameters.

<!-- PAGE_END: 21 -->
---

<!-- PAGE_START: 22 -->
## Page 22

### Page Text Content
Impact:  
The attacker only needs a static card URI to access and view sensitive card data within their active session, without requiring further 
authorization. This can lead to unauthorized exposure of sensitive financial information, resulting in data breaches, fraud, and compliance 
violations.  
CVE/CWE:  
CWE-639: Authorization Bypass Through User-Controlled Key  
Affected Asset:   
 
•  
https://in-Tatva-tr.stg.VERAHpay.ca/pf/vl/resource/*  
Recommendation:   
  
It is recommended to: Implement strict server-side authorization checks to ensure that MID and DMID values are properly mapped to the 
authenticated user session. Validate that users can only access resources explicitly assigned to them. Avoid relying solely on client-supplied 
identifiers for access control. Use indirect references or token-based validation to securely fetch card details.  
Reference: NA  
New or Repeat observation: New  
  
  
  
Proof of Concept:

<!-- PAGE_END: 22 -->
---

<!-- PAGE_START: 23 -->
## Page 23

### Embedded Visual Elements
[IMAGE_PAGE_23_FIG_1] *(Figure 1: page_23_fig_1.jpeg, 1305x491px)*

[IMAGE_PAGE_23_FIG_2] *(Figure 2: page_23_fig_2.jpeg, 1306x486px)*

### Page Text Content
6. Improper Error Handling  
Status: Open  
Severity: Low  
Detailed Observation:   
It was observed that when API endpoints are tampered with, the application responds with an HTTP 400 error that discloses detailed exception 
stack traces, and in cases where a duplicate entry is submitted, the API returns an HTTP 500 internal server error revealing database-related 
details such as table or column headers, which exposes internal implementation information to the user.  
Impact:

<!-- PAGE_END: 23 -->
---

<!-- PAGE_START: 24 -->
## Page 24

### Page Text Content
A malicious actor can leverage the exposed stack traces, database table names, and internal error details to gain insight into the application’s 
backend logic, database structure, and technologies in use, which can significantly aid in crafting targeted attacks such as SQL injection, privilege 
escalation, or further exploitation of the application.  
CVE/CWE:  
• 
CWE-209: Information Exposure Through an Error Message  
• 
CWE-200: Exposure of Sensitive Information to an Unauthorized Actor  
Affected Asset:   
• 
https://in-Tatva-tr.stg.VERAHpay.ca/*  
Recommendation:   
  
It is recommended to implement proper error handling by returning generic and user-friendly error messages for all API responses, while 
logging detailed error information securely on the server side, and ensuring that exception stack traces, database details, and internal system 
information are never exposed to end users.  
Reference: NA  
New or Repeat observation: New  
  
  
Proof of Concept:

<!-- PAGE_END: 24 -->
---

<!-- PAGE_START: 25 -->
## Page 25

### Embedded Visual Elements
[IMAGE_PAGE_25_FIG_1] *(Figure 1: page_25_fig_1.jpeg, 1389x486px)*

[IMAGE_PAGE_25_FIG_2] *(Figure 2: page_25_fig_2.jpeg, 1333x492px)*

### Page Text Content
7. Banner Grabbing  
Status: Open  
Severity: Low  
Detailed Observation:   
It was observed that by tampering with the API endpoint, the server returns an  error page that discloses internal details such as  Apache and 
its version. This unnecessary exposure allows attackers to fingerprint the technology stack.  
  
Impact:

<!-- PAGE_END: 25 -->
---

<!-- PAGE_START: 26 -->
## Page 26

### Embedded Visual Elements
[IMAGE_PAGE_26_FIG_1] *(Figure 1: page_26_fig_1.jpeg, 1307x546px)*

### Page Text Content
A malicious actor can use the disclosed server name and version information to understand the underlying technology stack and identify known 
weaknesses, making it easier to plan targeted attacks against the system.  
CVE/CWE:  
• 
CWE-209: Information Exposure Through an Error Message  
• 
CWE-200: Exposure of Sensitive Information  
Affected Asset:   
• 
https://in-Tatva-tr.stg.VERAHpay.ca/*  
Recommendation:   
  
It is recommended to configure the application and web server to suppress detailed error messages and remove server name and version 
information from all responses, including error pages, by using generic error messages instead.  
Reference: NA  
New or Repeat observation: New  
  
  
  
Proof of Concept:

<!-- PAGE_END: 26 -->
---

<!-- PAGE_START: 27 -->
## Page 27

<!-- PAGE_END: 27 -->
---

<!-- PAGE_START: 28 -->
## Page 28

### Table 28.1
|  | Severity Rating |
| --- | --- |
|  | Critical risk vulnerability has a high potential of impacting business operations leading to downtime or disruption and provides an attacker with privileged access, resulting in significant outage. If exploited, it has a direct impact on confidentiality, integrity or availability of organizational information. |
| Critical |  |
|  | High risk vulnerability indicates that successful exploitation of vulnerability may result in a significant impact to the confidentiality, integrity, or availability of the information accessible through the application/system or even the backend resources like databases, operating systems, etc. |
| High |  |
|  | Medium risk vulnerability reveals information about the application and its underlying infrastructure that can be used by an attacker in conjunction with another vulnerability to gain privileged control of the application or its underlying operating system. |
| Medium |  |
|  | Low risk vulnerability has the potential of revealing information about the system and may lead to unauthorized access to a system, leading to compromise. Higher work factors would be involved for exploiting this type of vulnerability. |
| Low |  |

### Table 28.2
| Risk Assessment Matrix |  |  |  |  |
| --- | --- | --- | --- | --- |
|  | Major | High | Critical | Critical |
| Impact of Vulnerability - Consequence | Moderate | Medium | Medium | High |
|  | Minor | Low | Medium | Medium |
|  |  | Hard | Moderate | Easy |
| Risk Severity = Impact x Probability |  |  |  |  |
|  |  | Pr | obability of Risk occurre | nce |

### Page Text Content
Appendices  
   
Risk Rating Criteria   
  
The risk rating is used to signify the level of risk due to gaps noted during the audit and is based on a qualitative criterion defined as follows:   
 
Severity Rating  
Critical  
Critical risk vulnerability has a high potential of impacting business operations leading to downtime or disruption and 
provides an attacker with privileged access, resulting in significant outage. If exploited, it has a direct impact on 
confidentiality, integrity or availability of organizational information.   
High  
High risk vulnerability indicates that successful exploitation of vulnerability may result in a significant impact to the 
confidentiality, integrity, or availability of the information accessible through the application/system or even the backend 
resources like databases, operating systems, etc.    
Medium  
Medium risk vulnerability reveals information about the application and its underlying infrastructure that can be used by 
an attacker in conjunction with another vulnerability to gain privileged control of the application or its underlying operating 
system.   
Low  
Low risk vulnerability has the potential of revealing information about the system and may lead to unauthorized access to 
a system, leading to compromise. Higher work factors would be involved for exploiting this type of vulnerability.   
   
   
To capture the risk rating, the following risk assessment matrix is used considering Impact and probability of risk in terms of ease of exploitation.    
Risk Assessment Matrix  
Impact of Vulnerability - Consequence  
Major  
High  
Critical  
Critical  
Moderate  
Medium  
Medium  
High  
Minor  
Low  
Medium  
Medium  
Risk Severity = Impact x Probability  
Hard  
Moderate  
Easy  
Pr obability of Risk occurre nce  
Please note: Risk rating will also depend on the business criticality of the asset.

<!-- PAGE_END: 28 -->
---

<!-- PAGE_START: 29 -->
## Page 29

### Page Text Content
END OF DOCUMENT

<!-- PAGE_END: 29 -->
---