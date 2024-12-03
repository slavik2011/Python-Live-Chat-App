# This file contains configurations that are safe to change and will not harm your program at all. To change it you have to fork this repo and deploy your fork.

# This configuration contains different types of settings, always read descriptions and comments before changing any parameter.

class rooms:
  pass

class messages:
  pass

class security:
  pass

class storage:
  pass

class colors:
  pass

# CONFIGURATION - ROOMS
rooms.max_members = 0 # set 0 to make it infinite
rooms.room_code_length = 6 # set ups how many symbols random-generated room codes contain
rooms.auto_deleting_rate = 3600 # 3600 means 3600 seconds means 1 hour of unactivity
rooms.auto_deleting_checking_rate = 60 # 60 means 60 seconds means 1 minute (rooms would be checked for unactivity every 1 minute)

# CONFIGURATION - MESSAGES
messages.max_symbols = 120 # set 0 to make it infinite
messages.message_delay = 0.5 # set 0 to remove delay

# CONFIGURATION - SECURITY
security.secret_code_length = 12 # sets length of the secret code used to login into ADMIN room or encrypt connections

# CONFIGURATION - STORAGE
storage.image_compressing_rate = 20 # 20 means 20% of default image quality
storage.video_compressing_rate = 20 # 20 means 20k bitrate

# CONFIGURATION - COLORS
colors.color_codes = {
    "<1111>": "#4465fc",
    "<201124>": "rainbow",
    "<228>": "#de1d1d",
    "<1231>": "#00ff2e",
    "<security333>": "#e455e2",
} # color codes used for getting colors for your chat
