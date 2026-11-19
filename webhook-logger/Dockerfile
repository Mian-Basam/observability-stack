FROM python:3.12-alpine
WORKDIR /srv
COPY app.py .
RUN adduser -S -u 10001 app
USER app
EXPOSE 9095
CMD ["python", "-u", "app.py"]
