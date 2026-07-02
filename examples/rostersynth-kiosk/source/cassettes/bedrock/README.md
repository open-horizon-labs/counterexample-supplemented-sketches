# Bedrock live snapshots

Frozen Oracle B output from `scripts/record_bedrock_cassettes.sh` (live AWS Bedrock Converse).

These prove the live path and pin model behavior at recording time. **CI gates** use `../cassettes/*.json` (golden-aligned, except intentional CE on `roster.new_period.undersched.v1`).

Re-record after prompt or model changes:

```bash
aws sso login --profile review
./scripts/record_bedrock_cassettes.sh
```

Compare live vs golden:

```bash
bench oracle roster.kiosk_double_booking.v1 --llm bedrock
cat cassettes/roster.kiosk_double_booking.v1.json
```
