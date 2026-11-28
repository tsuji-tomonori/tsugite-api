"""問い合わせ画面の部品とルートを定義する。"""

from actions.inquiries import load_inquiries
from components.inquiries import inquiries
from routing.screen_registry import Screen

SCREENS = (Screen("inquiries", "問い合わせ", inquiries, load_inquiries, group="ヘルプ", order=90),)
