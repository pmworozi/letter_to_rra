def generate_letter(profile, language="en", months=None, initial_payment=None):
    from datetime import date
    import random

    today = date.today().strftime("%d/%m/%Y")

    # Safe defaults (prevents broken letters)
    months = months or "[not provided]"
    initial_payment = initial_payment or "[not provided]"

    # Reference number generator
    def generate_reference():
        rand = random.randint(1000, 9999)
        return f"LTR-{date.today().strftime('%Y%m%d')}-{rand}"

    reference_no = generate_reference()

    if language == "rw":
        return f"""
{profile.name}
TIN: {profile.tin}
Tel: {profile.phone}
Email: {profile.email}

Date: {today}
Inomero y'inyandiko: {reference_no}


Komiseri Wungirije ushinzwe gucunga ibirarane
KIGALI


Impamvu: gusaba kwishyura mu byiciro


Nyakubahwa Komiseri,

Nanditse nsaba kwishyura mu byiciro umusoro mbereyemo RRA.
Nkaba nifuza kwishyura uwo musoro mu {months}.

Nkuko nabisabwe, nkaba nishyuye icyiciro cya mbere kingana na {initial_payment}.

Mu gihe ngitegereje igisubizo cyanyu cyiza mbaye mbashimiye.


{profile.name}
"""
    else:
        return f"""
{profile.name}
TIN: {profile.tin}
Tel: {profile.phone}
Email: {profile.email}

Date: {today}
Reference: {reference_no}


To: Deputy Commissioner in charge of Arrears Management
KIGALI


Subject: Request for installment payment


Dear Sir/Madam,

I am writing to request permission to pay my outstanding tax liabilities in installments.

I propose to settle the amount over a period of {months} months.

As required, I have already made an initial payment of {initial_payment}.

While awaiting your positive response, I thank you in advance.


Yours faithfully,

{profile.name}
"""