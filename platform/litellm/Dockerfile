FROM litellm/litellm:v1.87.1

ADD https://bootstrap.pypa.io/get-pip.py /tmp/get-pip.py
RUN python /tmp/get-pip.py && python -m pip install --no-cache-dir korcen

COPY config.yaml custom_guardrail.py /app/
