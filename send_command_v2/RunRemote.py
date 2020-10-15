import boto3
import os
import json

class RunRemoteScriptException(Exception):
    """
    This is a custom exception to raise.
    """
    pass

def run_remote_script(event, context):
    """
    This lambda function is the target of a CloudWatch Scheduled Event. It
    calls the SSM SendCommand API action and asks it to run the
    AWS-RunRemoteScript document on instances tagged with tagKey:tagValue. The
    remote script resides in github. This lambda calls the tar-and-store
    script.

    In its operating environment are the variables:
    tagKey, tagValue => the instance selection criteria
    appEnv => the instance's environment (dev, test, prod, etc.)
              This helps us create an s3 key in the form bucket/app/env/...
    bucket => the s3 bucket where we'll store the archive
    tarPaths => the files and directories we'd like to archive
    tokenInfo => the path to the parameter store secure string containing
                 the github access key.
    ghOwner => the owner of the GH repository
    ghRepo => the name of the GH repository
    ghPath => the path to the script
    """
    print("### Starting")
    print("### Event:")
    print("{}".format(event))

    ssm_client = boto3.client('ssm')

    bucket = os.environ.get('bucket', default='va-backups.lib.fsu.edu')
    tar_paths = os.environ.get('tarPaths', default=None)
    tag_key = os.environ.get('tagKey', default='Name')
    tag_value = os.environ.get('tagValue', default='')
    app_env = os.environ.get('appEnv', default=None)
    token_info = os.environ.get('tokenInfo', default=None)
    gh_owner = os.environ.get('ghOwner', default='fsulib')
    gh_repo = os.environ.get('ghRepo', default='remote-scripts')
    gh_path = os.environ.get('ghPath', default=None)

    print("### Environment:")
    print(os.environ)

    try:
        # Fail one or more of the following aren't present.
        if app_env is None:
            raise RunRemoteScriptException("No app_env parameter provided.")
        if token_info is None:
            raise RunRemoteScriptException("No GH token parameter provided.")
        if gh_path is None:
            raise RunRemoteScriptException("No GH path provided.")
        if tar_paths is None:
            raise RunRemoteScriptException("Nothing to tar. Why bother?.")

        # Ugly, but seems necessary: .format() removes one set of outer
        # curly brackets, which keeps the parameter lookup from working.
        token_info_string = '{{ ' + 'ssm-secure:' + token_info + ' }}'

        # Dump into a string later; the 'sourceInfo' parameter requires it.
        source_info_dict = {
                "tokenInfo": token_info_string,
                "owner": gh_owner,
                "repository": gh_repo,
                "path": gh_path
                }

        # tar-and-store: identifier bucket tar_paths
        command_line = " ".join(["/bin/bash",
                                os.path.basename(gh_path),
                                tag_value,
                                app_env,
                                bucket,
                                tar_paths])

        print("### command_line: {}".format(command_line))
        print("### sourceInfo:")
        print("{}".format(json.dumps(source_info_dict)))

        send_command_params = {
                "DocumentName": "AWS-RunRemoteScript",
                "Targets": [
                    {
                        "Key": "tag:{}".format(tag_key),
                        "Values": [
                            tag_value
                            ]
                        }
                    ],
                "Comment": 'Scheduled database backup run.',
                "Parameters": {
                    "sourceType": ["GitHub"],
                    "commandLine": [command_line],
                    "sourceInfo": [json.dumps(source_info_dict)]
                    }
                }
        
        print("### Parameters:")
        print(send_command_params)

        ssm_client.send_command(**send_command_params)
    except RunRemoteScriptException as e:
        raise
    except Exception as e:
        raise RunRemoteScriptException("Something weird happened: {}".format(e))

