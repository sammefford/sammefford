# Username is your ldap ID, not your email address. Use "username" instead of "username@adobe.com"
export ARTIFACTORY_USER='smefford'

# API Key from: https://artifactory.corp.adobe.com/ui/admin/artifactory/user_profile
export ARTIFACTORY_API_KEY=`cat ~/.ssh/artifactory_api_key`

# Cloud API Key from: https://artifactory-uw2.adobeitc.com/ui/admin/artifactory/user_profile
export ARTIFACTORY_CLOUD_API_KEY=`cat ~/.ssh/artifactory_cloud_api_key`

# From `wf artifactory creds`
ADOBE_ARTIFACTORY_USER=smefford
ADOBE_ARTIFACTORY_API_TOKEN=$ARTIFACTORY_CLOUD_API_KEY
ARTIFACTORY_INSTANCE=adobe

# From sitting with Jason Carrick
export ARTIFACTORY_API_TOKEN=$ARTIFACTORY_API_KEY

# instructions from https://devhome.corp.adobe.com/docs/default/component/hz/docs/guides/onboarding/individual/getting-started
export SDKROOT=$(xcrun --sdk macosx --show-sdk-path)
export PATH="/opt/homebrew/bin:/Library/Developer/CommandLineTools/usr/bin:$PATH"
# Github token for Horizon
export GH_AUTH_TOKEN=`cat ~/.ssh/git_corp_adobe_com_horizon`

# from `brew install nvm`
export NVM_DIR="$HOME/.nvm"
  [ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"  # This loads nvm
  [ -s "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm" ] && \. "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm"  # This loads nvm bash_completion

# from https://wiki.corp.adobe.com/spaces/AWF/pages/3202412793/AI+Dev+US+Onboarding
#export PATH="/opt/homebrew/anaconda3/bin:$PATH"

# User-local tools and Claude session logging wrappers.
export PATH="$HOME/.local/bin:$PATH"


# attempt to fix the bracketed paste mode in cmux
unset zle_bracketed_paste
