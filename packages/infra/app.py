# CDKアプリを起動する。
from aws_cdk import App
from src.stack import CatalogStack

app = App()
CatalogStack(app, "TsugiteApi")
app.synth()
