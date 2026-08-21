FROM python:3.12-slim

WORKDIR /app
COPY support_ticket_ai support_ticket_ai
COPY examples examples
COPY tests tests
COPY scripts scripts
RUN mkdir -p artifacts

ENTRYPOINT ["python", "-m", "support_ticket_ai.demo"]
CMD ["--scenario", "all"]

