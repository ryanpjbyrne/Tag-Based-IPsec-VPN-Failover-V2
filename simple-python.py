import yaml 

with open('meraki_parameters.yml','r') as ymlfile:
    cfg=yaml.load(ymlfile)

print (cfg)
print(cfg['meraki']['api_key'])
