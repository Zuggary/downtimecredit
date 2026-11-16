"""Deadline data and the date functions shared by the letter desk and the two state guides (TF12).
Each day count is the one the guide already states from the statute; where the rule cannot be counted, the note says so."""
import json

DEPOSIT_DUE = {
    "ny": (14, "New York: the landlord's 14 days end, by this site's count"),
    "tx": (30, "Texas: the 30th day after you left, by this site's count"),
    "oh": (30, "Ohio: the landlord's 30 days end, by this site's count"),
    "nc": (30, "North Carolina: the landlord's 30 days end, by this site's count (the statute allows more time in some cases)"),
    "mi": (30, "Michigan: 30 days for a notice of damages end, by this site's count"),
    "fl": (15, "Florida: if the landlord keeps nothing, the 15 days end, by this site's count (a landlord who means to keep some has 30 days to send notice by certified mail)"),
}
DEPOSIT_NONE = {"ca": "California's 21 days start from a point the statute ties to notices and the lease, so this site shows the rule and no date."}
PAY_DUE = {
    ("tx", "discharged"): (6, "Texas: the sixth day after discharge, by this site's count"),
}
PAY_PAYDAY = {("tx", "quit"): "Texas: the next regularly scheduled payday", ("ny", "any"): "New York: the regular pay day for the pay period in which the job ended",
              ("nc", "any"): "North Carolina: the next regular payday", ("wa", "any"): "Washington: the end of the established pay period"}
PAY_NONE = {("ca", "discharged"): "California: due immediately when an employer discharges you, so there is no later date to mark.",
            ("ca", "quit"): "California: within 72 hours of quitting, or at once with 72 hours' notice. This site counts days, not hours, so it shows the rule and no date.",
            ("mi", "discharged"): "Michigan: as soon as the amount can with due diligence be determined. The rule names no day count, so there is no date.",
            ("mi", "quit"): "Michigan: as soon as the amount can with due diligence be determined. The rule names no day count, so there is no date."}

DEPOSIT_DUE_JS = "function (v, mine) {\n    if (!v.state) return { note: \"Pick a state to see the landlord's deadline.\" };\n    if (NONE[v.state]) return { note: NONE[v.state] };\n    var r = DUE[v.state]; if (!r) return { note: \"This site has not checked that state, so it shows no date.\" };\n    if (!v.out) return { note: \"Type the day you moved out to see the date.\" };\n    var d = D.addDays(v.out, r[0]); if (!d) return null;\n    return { date: d, label: \"Landlord's deadline\", line: r[1], title: \"Deposit: landlord's deadline (this site's count)\", description: r[1] + \". Counted from the move-out day you typed. The statute has conditions and exceptions this count does not cover. Not legal advice.\", alarm: \"days to the landlord's deposit deadline\" };\n  }"
PAY_DUE_JS = "function (v, mine) {\n    if (!v.state) return { note: \"Pick a state to see the deadline.\" };\n    if (v.state === \"other\") return { note: \"This site has not checked that state, so it shows no date.\" };\n    if (!v.how) return { note: \"Pick how the job ended to see the deadline.\" };\n    var k = v.state + \"|\" + v.how, ka = v.state + \"|any\";\n    if (NONE[k]) return { note: NONE[k] };\n    var r = DUE[k];\n    if (r) { if (!v.end) return { note: \"Type your last day of work to see the date.\" }; var d = D.addDays(v.end, r[0]); return d ? { date: d, label: \"Pay due by\", line: r[1], title: \"Final pay due (this site's count)\", description: r[1] + \". Counted from the last day you typed. The statute has conditions and exceptions. Not legal advice.\", alarm: \"days to the final pay deadline\" } : null; }\n    var p = PAYDAY[k] || PAYDAY[ka];\n    if (p) { if (!v.payday) return { note: p + \". Type that payday to mark it on your calendar.\" }; return { date: v.payday, label: \"Pay due by\", line: p + \" (the payday you typed)\", title: \"Final pay: the payday the rule names\", description: p + \". This is the payday you typed. The statute has conditions and exceptions. Not legal advice.\", alarm: \"days to the payday\" }; }\n    return { note: \"This site shows no date for that case.\" };\n  }"



def deposit_vars() -> str:
    return f"var DUE = {json.dumps(DEPOSIT_DUE)}, NONE = {json.dumps(DEPOSIT_NONE)};"


def pay_vars() -> str:
    return (f"var DUE = {json.dumps({k[0] + '|' + k[1]: v for k, v in PAY_DUE.items()})}, NONE = {json.dumps({k[0] + '|' + k[1]: v for k, v in PAY_NONE.items()})}, "
            f"PAYDAY = {json.dumps({k[0] + '|' + k[1]: v for k, v in PAY_PAYDAY.items()})};")
