sudo mkdir -p /var/log/discord-iam
#User will need to change to a service account
sudo chown -R $USER:$USER /var/log/discord-iam

#Set service account and permissions
sudo useradd --system --create-home --shell /usr/sbin/nologin discord-iam
sudo chown -R discord-iam:discord-iam /opt/iam_discord
sudo chown -R discord-iam:discord-iam /var/log/discord-iam

#Test line to run from crontab with service account
sudo -u discord-iam bash -c 'cd /opt/iam_discord/app && /opt/iam_discord/environments/iam_discord/bin/python -m discord.get_discord_server_data'

#Run crontab
sudo crontab -u discord-iam -e

#crontab line
0 * * * * cd /opt/iam_discord/app && /opt/iam_discord/environments/iam_discord/bin/python -m discord.get_discord_server_data