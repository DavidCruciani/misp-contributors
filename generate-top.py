import datetime
import redis
redcon = redis.StrictRedis(host='localhost', port=6379, db=11, decode_responses=True)

output = '---\n'
output += 'layout: page\n'
output += 'title: MISP contributors per repository\n'
output += 'permalink: /contributors/\n'
output += 'toc: true\n'
output += '---\n\n'


url_github = 'https://www.github.com/MISP/'
url_user = 'https://www.github.com/'
repo_to_skip = ['cti-python-stix2', 'SwiftCodes']

all_contributors = redcon.zcard('topversatile')

output += f"# {all_contributors} Contributors ({datetime.datetime.now().strftime('%Y-%m-%d')}) \n\n"

for user in redcon.zrevrange('topversatile', 0, -1):
    gravatar = redcon.get("a:{}".format(user))
    output += f"[![{user}]({gravatar} \"{{:height='36px' width='36px'}}\")]({url_user}{user})"
output += "\n"

all_contributors = redcon.zcard('topcommit')

output += f"## Top {all_contributors}  contributors per commit \n\n"

for user in redcon.zrevrange('topcommit', 0, -1):
    gravatar = redcon.get("a:{}".format(user))
    output += f"[![{user}]({gravatar} \"{{:height='36px' width='36px'}}\")]({url_user}{user})"

output += "\n"

for repository in sorted(redcon.smembers('repositories')):
    if repository in repo_to_skip:
        continue
    card = redcon.zcard('r:{}'.format(repository))
    output += f"# {repository} with {card} contributors \n\n"
    output += f"The repository [{repository}]({url_github}{repository}) is part of the MISP project and has the following top contributors \n\n"
    output += "| username | total commits |\n"
    output += "|:--------:|:-------------:|\n"
    for top in redcon.zrevrange('r:{}'.format(repository), 0, -1, withscores=True):
        output += f"|[{top[0]}]({url_user}{top[0]})|{int(top[1])}|\n"
    output += "\n"

# print (output)
with open("contributors.md", "w") as write_file:    write_file.write(output)