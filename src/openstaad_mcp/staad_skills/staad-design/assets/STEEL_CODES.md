# Steel Design Codes Reference

Code numbers for `design.CreateDesignBrief(codeNumber)`.

## Common Steel Codes

| Code | Standard |
|------|----------|
| 1067 | ANSI/AISC 360-16 |
| 1061 | ANSI/AISC 360-10 |
| 1045 | ANSI/AISC 360-05 |
| 1004 | BS 5950-1:2000 |
| 1220 | BS EN 1993-1-1:2005 (Eurocode 3) |
| 1032 | IS 800 2007 LSD |
| 1149 | AS 4100 |
| 1182 | CSA S16-14 |

## All Steel Code Indices

### US Codes
| Code | Standard |
|------|----------|
| 1001 | AASHTO ASD |
| 1002 | AISC ASD |
| 1011 | AISC LRFD |
| 1044 | AASHTO LRFD |
| 1045 | ANSI/AISC 360-05 |
| 1061 | ANSI/AISC 360-10 |
| 1067 | ANSI/AISC 360-16 |
| 1068 | AISI S100-2016 |
| 1016 | API 2A-WSD |
| 1020 | ASCE 10-97 |
| 1060 | ASCE 52 |

### British & European
| Code | Standard |
|------|----------|
| 1004 | BS 5950-1:2000 |
| 1005 | BS 5400:Part 3:1982 |
| 1033 | BS 5950-5:1998 |
| 1220 | BS EN 1993-1-1:2005 |

### Canadian
| Code | Standard |
|------|----------|
| 1006 | CAN/CSA-S16-01 |
| 1062 | Canadian S16_09 |
| 1065 | Canadian S16_14 |
| 1069 | Canadian S16_19 |

### Indian
| Code | Standard |
|------|----------|
| 1009 | IS 800 1984, ASD |
| 1032 | IS 800 2007, LSD |
| 1052 | IS 800 2007, WSD |

### Australian & NZ
| Code | Standard |
|------|----------|
| 1003 | AS 4100-1998 |
| 1066 | NZS3404_1997 |

### Other
| Code | Standard |
|------|----------|
| 1007 | French CM66 1977 |
| 1008 | DIN 18 800 Part 1 |
| 1010 | Japan AIJ 2002 |
| 1210 | Japan AIJ 2005 |
| 1025 | Russia SNiP 2.23-81* 1990 |
| 1063 | Russia SP 16.13330.2011 |
| 1034 | South Africa SANS 10162-1:2011 |

## Steel Design Parameters

| Parameter | Description | Example Value |
|-----------|-------------|---------------|
| BEAM | Member is a beam | "1" |
| FYLD | Yield strength | "250" (MPa) |
| FU | Ultimate strength | "400" (MPa) |
| KY | Effective length factor Y | "0.85" |
| KZ | Effective length factor Z | "1.0" |
| LY | Unbraced length Y | "3000" (mm) |
| LZ | Unbraced length Z | "3000" (mm) |
| CB | Bending coefficient | "1.0" |
| UNL | Unsupported length | "6000" (mm) |
| TRACK | Output detail level | "2" |
| DMAX | Maximum section depth | "600" (mm) |
| DMIN | Minimum section depth | "200" (mm) |
| DFF | Deflection limit (span/value) | "300" |
| RATIO | Allowable ratio | "1.0" |
| MAIN | Main member check | "1" |
