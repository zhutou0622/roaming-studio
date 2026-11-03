"""Synthetic TAP3 file generator (test data / demo files).

Everything is produced through the ASN.1 schema, so the output is a
structurally valid TAP3.11 file that round-trips through the decoder.
"""
from __future__ import annotations

import random
from typing import Dict, List

from . import ber, builder
from .tapfile import Tap3Document



def _sub(imsi: str, msisdn: str, op: str = "26201") -> dict:
    return {"simChargeableSubscriber": {"imsi": imsi, "msisdn": msisdn}}


def mo_call(rng: random.Random, idx: int, start: str, charge: int) -> dict:
    imsi = f"26201123456{idx:02d}"
    msisdn = f"49171000{idx:04d}"
    return {
        "basicCallInformation": {
            "chargeableSubscriber": _sub(imsi, msisdn),
            "rapFileSequenceNumber": "00001",
            "destination": {"calledNumber": "4917222000"},
            "destinationNetwork": "26202",
            "callEventStartTimeStamp": {"localTimeStamp": start, "utcTimeOffsetCode": "1"},
            "totalCallEventDuration": rng.randint(10, 600),
            "causeForTerm": 0,
        },
        "locationInformation": {
            "networkLocation": {"recEntityCode": "1", "locationArea": 1201, "cellId": 4321}
        },
        "equipmentIdentifier": {"imei": "35693803564380"},
        "basicServiceUsedList": [{
            "basicService": {"serviceCode": {"teleServiceCode": "11"}},
            "chargingTimeStamp": {"localTimeStamp": start, "utcTimeOffsetCode": "1"},
            "chargeInformationList": [{
                "chargedItem": "1",
                "callTypeGroup": {"callTypeLevel1": 1},
                "chargeDetailList": [{
                    "chargeType": "10",
                    "charge": charge,
                    "chargeableUnits": 60,
                    "chargedUnits": 60,
                }],
                "taxInformation": [{"taxCode": 1, "taxValue": charge * 190 // 1000,
                                    "taxableAmount": charge}],
            }],
        }],
    }


def mt_call(rng: random.Random, idx: int, start: str, charge: int) -> dict:
    return {
        "basicCallInformation": {
            "chargeableSubscriber": _sub(f"26201987654{idx:02d}", f"49172000{idx:04d}"),
            "rapFileSequenceNumber": "00001",
            "callOriginator": {"callingNumber": "4930123456", "clirIndicator": 0},
            "originatingNetwork": "26202",
            "callEventStartTimeStamp": {"localTimeStamp": start, "utcTimeOffsetCode": "1"},
            "totalCallEventDuration": rng.randint(5, 300),
            "causeForTerm": 0,
        },
        "locationInformation": {
            "networkLocation": {"recEntityCode": "1", "locationArea": 1201, "cellId": 4322}
        },
        "basicServiceUsedList": [{
            "basicService": {"serviceCode": {"teleServiceCode": "11"}},
            "chargeInformationList": [{
                "chargedItem": "1",
                "chargeDetailList": [{"chargeType": "10", "charge": charge,
                                      "chargeableUnits": 60, "chargedUnits": 60}],
            }],
        }],
    }


def gprs_call(rng: random.Random, idx: int, start: str, charge: int) -> dict:
    return {
        "gprsBasicCallInformation": {
            "chargeableSubscriber": {
                "chargeableSubscriber": _sub(f"26201555500{idx:02d}", f"49173000{idx:04d}"),
                "pdpAddress": "10.20.30.40",
            },
            "rapFileSequenceNumber": "00001",
            "gprsDestination": {"accessPointNameNI": "internet"},
            "callEventStartTimeStamp": {"localTimeStamp": start, "utcTimeOffsetCode": "1"},
            "totalCallEventDuration": rng.randint(30, 3600),
            "causeForTerm": 0,
            "chargingId": 900000 + idx,
        },
        "gprsLocationInformation": {
            "gprsNetworkLocation": {"recEntity": ["1"], "locationArea": 1201, "cellId": 4400}
        },
        "gprsServiceUsed": {
            "dataVolumeIncoming": 1024 * rng.randint(1, 50),
            "dataVolumeOutgoing": 4096 * rng.randint(1, 50),
            "chargeInformationList": [{
                "chargedItem": "1",
                "chargeDetailList": [{"chargeType": "20", "charge": charge,
                                      "chargeableUnits": 1, "chargedUnits": 1}],
            }],
        },
    }


def build_spec(n_events: int = 6, seed: int = 7, sender: str = "26201",
               recipient: str = "22801", currency: str = "EUR") -> dict:
    rng = random.Random(seed)
    events: List[dict] = []
    total = 0
    times = ["2024011509" + f"{10 + i:02d}" + "00" for i in range(24)]
    i = 0
    while len(events) < n_events:
        i += 1
        kind = ("mobileOriginatedCall", "mobileTerminatedCall", "gprsCall")[(i - 1) % 3]
        charge = rng.randint(50, 900)
        start = times[(i - 1) % len(times)]
        if kind == "mobileOriginatedCall":
            ev = {"mobileOriginatedCall": mo_call(rng, i, start, charge)}
        elif kind == "mobileTerminatedCall":
            ev = {"mobileTerminatedCall": mt_call(rng, i, start, charge)}
        else:
            ev = {"gprsCall": gprs_call(rng, i, start, charge)}
        events.append(ev)
        total += charge
    return {
        "transferBatch": {
            "batchControlInfo": {
                "sender": sender,
                "recipient": recipient,
                "fileSequenceNumber": "00042",
                "fileCreationTimeStamp": {"localTimeStamp": "20240115101000",
                                          "utcTimeOffset": "+0100"},
                "transferCutOffTimeStamp": {"localTimeStamp": "20240115095959",
                                            "utcTimeOffset": "+0100"},
                "fileAvailableTimeStamp": {"localTimeStamp": "20240115101030",
                                           "utcTimeOffset": "+0100"},
                "specificationVersionNumber": 3,
                "releaseVersionNumber": 11,
                "fileTypeIndicator": "T",
            },
            "accountingInfo": {
                "taxation": [{"taxCode": 1, "taxType": "01", "taxRate": "1900000"}],
                "localCurrency": currency,
                "tapCurrency": currency,
                "tapDecimalPlaces": 3,
            },
            "networkInfo": {
                "utcTimeOffsetInfo": [{"utcTimeOffsetCode": "1", "utcTimeOffset": "+0100"}],
                "recEntityInfo": [{"recEntityCode": "1", "recEntityType": 5,
                                   "recEntityId": {"mscId": "MSC-01"}}],
            },
            "messageDescriptionInfo": [
                {"messageDescriptionCode": "1", "messageDescription": "Peak"}
            ],
            "callEventDetails": events,
            "auditControlInfo": {
                "earliestCallTimeStamp": {"localTimeStamp": "20240115091000",
                                          "utcTimeOffset": "+0100"},
                "latestCallTimeStamp": {"localTimeStamp": "20240115093300",
                                        "utcTimeOffset": "+0100"},
                "totalCharge": total,
                "totalTaxValue": total * 190 // 1000,
                "totalDiscountValue": 0,
                "callEventDetailsCount": len(events),
            },
        }
    }


def make_document(n_events: int = 6, seed: int = 7, sender: str = "26201",
                  recipient: str = "22801", currency: str = "EUR") -> Tap3Document:
    from .tapfile import all_modules
    module = all_modules().get("TAP0311.asn")
    if module is None:
        raise RuntimeError("TAP0311 schema missing")
    spec = build_spec(n_events=n_events, seed=seed, sender=sender, recipient=recipient,
                      currency=currency)
    root = builder.build(module, "DataInterChange", spec)
    data = ber.encode_file(root)
    return Tap3Document(data, filename=f"generated_{n_events}_{seed}.tap3")


def write_sample(path: str, n_events: int = 6, seed: int = 7, **kw) -> str:
    doc = make_document(n_events=n_events, seed=seed, **kw)
    doc.save(path)
    return path
