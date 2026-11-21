from aws_cdk import App
from src.infra_app.stack import CatalogStack

app=App()
CatalogStack(app,"TsugiteApi")
app.synth()
