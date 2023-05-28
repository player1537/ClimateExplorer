"""

"""

from __future__ import annotations

from flask import Flask

from .code import app as code_app
from .flow import app as flow_app


app = Flask(__name__)
app.register_blueprint(
    code_app,
    url_prefix='/code',
)
app.register_blueprint(
    flow_app,
    url_prefix='/flow',
)


def main():
    app.run(debug=True)


def cli():
    import argparse

    parser = argparse.ArgumentParser()
    args = vars(parser.parse_args())

    main(**args)


if __name__ == '__main__':
    cli()
