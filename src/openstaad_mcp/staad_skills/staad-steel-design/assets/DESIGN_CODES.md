# STAAD.Pro Steel Design Codes Reference

This file contains design code indices for `CreateSteelDesignCommand()`.

**Note:** The complete parameter tables are extensive (1000+ lines). Use Python introspection for full details:

```python
help(staad.Command.CreateSteelDesignCommand)
```

## Design Code Indices (NDesignCode)

### US Codes

| Code | Description      |
| ---- | ---------------- |
| 1001 | AASHTO ASD       |
| 1002 | AISC ASD         |
| 1011 | AISC LRFD        |
| 1044 | AASHTO LRFD      |
| 1045 | ANSI/AISC 360-05 |
| 1061 | ANSI/AISC 360-10 |
| 1067 | ANSI/AISC 360-16 |
| 1068 | AISI S100-2016   |
| 1016 | API 2A-WSD       |
| 1020 | ASCE 10-97       |
| 1060 | ASCE 52          |

### British & European Codes

| Code | Description         |
| ---- | ------------------- |
| 1004 | BS 5950-1:2000      |
| 1005 | BS 5400:Part 3:1982 |
| 1033 | BS 5950-5:1998      |
| 1220 | BS EN 1993-1-1:2005 |

### Canadian Codes

| Code | Description     |
| ---- | --------------- |
| 1006 | CAN/CSA-S16-01  |
| 1027 | Canada S136-94  |
| 1062 | Canadian S16_09 |
| 1065 | Canadian S16_14 |
| 1069 | Canadian S16_19 |

### Australian & NZ Codes

| Code | Description  |
| ---- | ------------ |
| 1003 | AS 4100-1998 |
| 1066 | NZS3404_1997 |

### Indian Codes

| Code | Description      |
| ---- | ---------------- |
| 1009 | IS 800 1984, ASD |
| 1032 | IS 800 2007, LSD |
| 1052 | IS 800 2007, WSD |
| 1028 | IS 801 1975      |
| 1029 | IS 802 1995      |

### Other Codes

| Code | Description                    |
| ---- | ------------------------------ |
| 1007 | French CM66 1977               |
| 1008 | DIN 18 800 Part 1              |
| 1010 | Japan AIJ 2002                 |
| 1210 | Japan AIJ 2005                 |
| 1012 | Norway NS 3472 2001            |
| 1014 | Norway NPD 1993                |
| 1025 | Russia SNiP 2.23-81\* 1990     |
| 1063 | Russia SP 16.13330.2011        |
| 1221 | Russia SP 16.13330.2017        |
| 1030 | Mexico NTC 1987                |
| 1034 | South Africa SANS 10162-1:2011 |
| 1064 | South Africa SANS10162-1:1993  |

### ASME NF Codes

| Code      | Description                  |
| --------- | ---------------------------- |
| 1046-1053 | ASME NF 3000 (various years) |

## Common Design Command Numbers (NCommandNo)

These are consistent across most codes:

| Command | NCommandNo | Description                   |
| ------- | ---------- | ----------------------------- |
| CODE    | 9010       | Design code specification     |
| BEAM    | 9380       | Member is a beam              |
| FYLD    | 9100       | Yield strength                |
| FU      | 9705       | Ultimate strength             |
| KY      | 9240       | Effective length factor (Y)   |
| KZ      | 9250       | Effective length factor (Z)   |
| LY      | 9130       | Unbraced length (Y)           |
| LZ      | 9140       | Unbraced length (Z)           |
| CB      | 9280       | Bending coefficient           |
| DFF     | 9210       | Deflection limit (span/value) |
| DJ1     | 9390       | Deflection check start joint  |
| DJ2     | 9400       | Deflection check end joint    |
| DMAX    | 9160       | Maximum depth                 |
| DMIN    | 9170       | Minimum depth                 |
| TRACK   | 9350       | Output detail level           |
| UNL     | 9150       | Unsupported length            |
| UNT     | 9650       | Top flange unbraced           |
| UNB     | 9660       | Bottom flange unbraced        |
| MAIN    | 9330       | Main member check             |
| RATIO   | 9360       | Allowable ratio               |
| PROFILE | 9520       | Section type/profile          |
| STIFF   | 9200       | Stiffener spacing             |

## Parameter Value Arrays

The `IntValues`, `FloatValues`, and `StringValues` arrays depend on the command:

- **BEAM=1**: `IntValues=[1]` (member is beam)
- **FYLD=250**: `FloatValues=[250.0]` (250 MPa yield)
- **KY=0.85**: `FloatValues=[0.85]`
- **TRACK=2**: `IntValues=[2]` (detailed output)

Consult the full docstring via `help()` for code-specific parameter requirements.
