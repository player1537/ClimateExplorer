"""

"""

from __future__ import annotations

from flask import Flask

from .flow import app as flow_app


app = Flask(__name__)
app.register_blueprint(
    flow_app,
    url_prefix='/flow',
)


def main():
    app.run()


def cli():
    import argparse

    parser = argparse.ArgumentParser()
    args = vars(parser.parse_args())

    main(**args)


if __name__ == '__main__':
    cli()
