"""Rebuild static Nunito Sans 900 / 700 / 300 from the variable font.

Only needed if the static TTFs are missing. Downloads the official variable
font from Google Fonts if assets/fonts/nunito_var.ttf is absent.
"""
import os, subprocess, sys
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
SRC = os.path.join(D, "nunito_var.ttf")
URL = ("https://raw.githubusercontent.com/google/fonts/main/ofl/nunitosans/"
       "NunitoSans%5BYTLC%2Copsz%2Cwdth%2Cwght%5D.ttf")

if not os.path.exists(SRC):
    subprocess.run(["curl", "-sSL", "--max-time", "60", "-o", SRC, URL], check=True)

for wght, name in [(900, "NunitoSans-Black.ttf"), (700, "NunitoSans-Bold.ttf"),
                   (300, "NunitoSans-Light.ttf")]:
    f = TTFont(SRC)
    instancer.instantiateVariableFont(
        f, {"wght": wght, "wdth": 100, "opsz": 12, "YTLC": 500}, inplace=True)
    f.save(os.path.join(D, name))
    print("wrote", name)
