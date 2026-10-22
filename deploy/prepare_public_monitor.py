"""Render reviewable local artifacts only; never calls AWS or starts a schedule."""

import argparse
import hashlib
import json
from pathlib import Path

ACCOUNT = "431988153216"
REGION = "ap-southeast-2"
NAME = "enter-public-https-monitor"
ALARM = "enter-public-https-unavailable"
PREFIX = "arn:aws:"
TOPIC = f"{PREFIX}sns:{REGION}:{ACCOUNT}:enter-production-alerts"
FUNCTION = f"{PREFIX}lambda:{REGION}:{ACCOUNT}:function:{NAME}"
GROUP = f"{PREFIX}scheduler:{REGION}:{ACCOUNT}:schedule-group/{NAME}"
LOG = f"{PREFIX}logs:{REGION}:{ACCOUNT}:log-group:/aws/lambda/{NAME}"


def policy(statements):
    return {"Version": "2012-10-17", "Statement": statements}


def allow(actions, resource, **extra):
    return {"Effect": "Allow", "Action": actions, "Resource": resource, **extra}


def trust(service, conditions=None):
    statement = {"Effect": "Allow", "Principal": {"Service": service}, "Action": "sts:AssumeRole"}
    if conditions:
        statement["Condition"] = conditions
    return policy([statement])


def documents():
    runtime = policy(
        [
            allow(
                "cloudwatch:PutMetricData",
                "*",
                Condition={
                    "StringEquals": {
                        "cloudwatch:namespace": "ENTER/PublicAvailability",
                        "aws:RequestedRegion": REGION,
                    }
                },
            ),
            allow(["logs:CreateLogStream", "logs:PutLogEvents"], LOG + ":log-stream:*"),
        ]
    )
    scheduler = policy([allow("lambda:InvokeFunction", FUNCTION)])
    scheduler_trust = trust(
        "scheduler.amazonaws.com",
        {
            "StringEquals": {
                "aws:SourceAccount": ACCOUNT,
                "aws:SourceArn": GROUP,
            }
        },
    )
    sns_statement = {
        "Sid": "ENTERPublicAvailabilityAlarm",
        "Effect": "Allow",
        "Principal": {"Service": "cloudwatch.amazonaws.com"},
        "Action": "sns:Publish",
        "Resource": TOPIC,
        "Condition": {
            "StringEquals": {"aws:SourceAccount": ACCOUNT},
            "ArnEquals": {
                "aws:SourceArn": f"arn:aws:cloudwatch:{REGION}:{ACCOUNT}:alarm:{ALARM}",
            },
        },
    }
    resources = {
        "Logs": {
            "Type": "AWS::Logs::LogGroup",
            "DeletionPolicy": "Retain",
            "UpdateReplacePolicy": "Retain",
            "Properties": {"LogGroupName": f"/aws/lambda/{NAME}", "RetentionInDays": 7},
        },
        "RuntimeRole": {
            "Type": "AWS::IAM::Role",
            "Properties": {
                "RoleName": "ENTER-PublicHttpsMonitor-Role",
                "AssumeRolePolicyDocument": trust("lambda.amazonaws.com"),
                "Policies": [{"PolicyName": "PublishAvailabilityOnly", "PolicyDocument": runtime}],
            },
        },
        "ScheduleRole": {
            "Type": "AWS::IAM::Role",
            "Properties": {
                "RoleName": "ENTER-PublicHttpsScheduler-Role",
                "AssumeRolePolicyDocument": scheduler_trust,
                "Policies": [{"PolicyName": "InvokeMonitorOnly", "PolicyDocument": scheduler}],
            },
        },
        "Probe": {
            "Type": "AWS::Lambda::Function",
            "DependsOn": "Logs",
            "Properties": {
                "FunctionName": NAME,
                "Runtime": "python3.12",
                "Handler": "index.handler",
                "Role": {"Fn::GetAtt": ["RuntimeRole", "Arn"]},
                "MemorySize": 128,
                "Timeout": 30,
                "Code": {
                    "ZipFile": Path(__file__).with_name("public_https_monitor.py").read_text()
                },
            },
        },
        "ScheduleGroup": {"Type": "AWS::Scheduler::ScheduleGroup", "Properties": {"Name": NAME}},
        "Schedule": {
            "Type": "AWS::Scheduler::Schedule",
            "Properties": {
                "Name": NAME,
                "GroupName": {"Ref": "ScheduleGroup"},
                "State": "DISABLED",
                "ScheduleExpression": "rate(5 minutes)",
                "FlexibleTimeWindow": {"Mode": "OFF"},
                "Target": {
                    "Arn": {"Fn::GetAtt": ["Probe", "Arn"]},
                    "RoleArn": {"Fn::GetAtt": ["ScheduleRole", "Arn"]},
                    "Input": "{}",
                    "RetryPolicy": {"MaximumEventAgeInSeconds": 60, "MaximumRetryAttempts": 0},
                },
            },
        },
        "AvailabilityAlarm": {
            "Type": "AWS::CloudWatch::Alarm",
            "Properties": {
                "AlarmName": ALARM,
                "AlarmDescription": "ENTER public HTTPS unavailable or probe missing",
                "Namespace": "ENTER/PublicAvailability",
                "MetricName": "Healthy",
                "Statistic": "Minimum",
                "Period": 300,
                "EvaluationPeriods": 2,
                "DatapointsToAlarm": 2,
                "Threshold": 1,
                "ComparisonOperator": "LessThanThreshold",
                "TreatMissingData": "breaching",
                "ActionsEnabled": False,
                "AlarmActions": [TOPIC],
                "OKActions": [TOPIC],
            },
        },
    }
    template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "ENTER off-host monitor only; schedule and alarm actions initially disabled",
        "Resources": resources,
    }
    return {
        "template.json": template,
        "runtime-policy.json": runtime,
        "runtime-trust.json": trust("lambda.amazonaws.com"),
        "scheduler-policy.json": scheduler,
        "scheduler-trust.json": scheduler_trust,
        "sns-policy-addition.json": sns_statement,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Never replace an earlier reviewed release directory.
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    checksums = []
    for name, value in documents().items():
        data = (json.dumps(value, indent=2) + "\n").encode()
        (args.output / name).write_bytes(data)
        checksums.append(f"{hashlib.sha256(data).hexdigest()}  {name}")
    (args.output / "SHA256SUMS").write_text("\n".join(checksums) + "\n")
    print("Local artifacts generated; no AWS API calls made.")


if __name__ == "__main__":
    main()
