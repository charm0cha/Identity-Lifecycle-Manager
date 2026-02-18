import requests
import os 
from dotenv import find_dotenv, load_dotenv
import time 
from datetime import datetime, timezone, timedelta
import logging
from datetime import datetime
import csv


log_filename = f'disable_accounts_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()  # Also print to console
    ]
)

logger = logging.getLogger(__name__)



load_dotenv(find_dotenv())

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
CLIENT_ID = os.getenv("CLIENT_ID")
AUDIENCE = f"https://{AUTH0_DOMAIN}/api/v2/"

MAXIMUM_DAYS = int(os.getenv("MAXIMUM_DAYS", "30"))
POLICY_START_STR = os.getenv("POLICY_START")
POLICY_START = datetime.fromisoformat(POLICY_START_STR).replace(tzinfo=timezone.utc)

# print(os.getenv("CLIENT_ID")) to ensure .env file is being loaded 


DRY_RUN = os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes")





def get_management_token():
    logger.info("Authenticating with Auth0...")
    url = f"https://{AUTH0_DOMAIN}/oauth/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET, 
        "audience": AUDIENCE,
        "grant_type":"client_credentials"
        }
    
    headers = { 'content-type': "application/json", "accept" : "application/json" }
    r = requests.post(url, json=payload, headers=headers, timeout=30)

    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        logger.error(f"Auth0 token request failed: {r.status_code} {r.text}")
        raise RuntimeError(f"Auth0 token request failed: {r.status_code} {r.text}")
    data = r.json()
    if "access_token" not in data:
        logger.error(f"No access_token in response: {data}")
        raise RuntimeError(f"No access_token in response: {data}")
    
    logger.info("")
    logger.info("Successfully obtained Auth0 management token - Authenticated.")
    logger.info("")
    return data["access_token"]


# to test token retrevial 
# if __name__ == "__main__":
#     token_test = get_management_token()
#     print(token_test)






def get_static_users():
    token = get_management_token()
    url = f"{AUDIENCE}users"

    headers = { 
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
        }
    
    # exclude certain domains
    included_domains = [ '@viooh.com'
        # '@jcdecaux.com', '@afadecaux.dk', '@igpdecaux.it', 
                    #  '@walldecaux.de', '@dunnhumby.com', '@gewista.at', '@afadecaux.dk'
                    ]
    included_queries = [f'email:*{domain}' for domain in included_domains]
    included_query_str = ' OR '.join(included_queries)
    query = (
        f'({included_query_str})'
        )
    

    per_page = 50 
    page = 0 
    total_fetched = 0

    logger.info("")
    logger.info("Fetching users from Auth0...")
    logger.info(f"Included domains: {', '.join(included_domains)}")
    logger.info("")

    while True:
        params = {
                "q" : query,
                "fields": "email,created_at,identities,user_id,last_login,blocked,app_metadata",
                 "include_fields" : "true",
                 "search_engine" : "v3",
                 "per_page": per_page,
                 "page": page,
                 "include_totals": "true"
            }
        
        response = requests.get(
            url,
            headers=headers, 
            params=params, 
            timeout=30
            )
        
        if response.status_code != 200:
            logger.error(f"[ERROR] users returned {response.status_code}")
            logger.error("Response text:")
            raise SystemExit(1)
        
        data = response.json()
        users = data.get("users", [])

        logger.info("")
        logger.info(f"Fetched page {page}: {len(users)} users")
        logger.info("")
        total_fetched += len(users)

        if not users:
            break #no more pages

        for user in users:
            yield user

        page += 1
        time.sleep(0.1)

    logger.info(f'Total users fetched:{total_fetched}')


# # test if list of users + created at date prints
# # def main():
# #     users = get_static_users()
# #     print(users)
# # if __name__ == "__main__":
# #     main()






def get_connection_type(identities):
    if not identities:
        return "Unknown"
    
    if len(identities) > 1:
        
        connections = [identity.get('connection', 'unknown') for identity in identities]
        return f"SSO/Linked ({', '.join(connections)})"
    
   
    return identities[0].get('connection', 'Unknown')





def save_report(accounts, filename='acc_disable_report.csv'):
    if not accounts:
        logger.info("No accounts to report")
        return
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'script_run_date',
            'email', 
            'user_id', 
            'created_at', 
            'days_old', 
            'days_over_threshold', 
            'connection_type', 
            'existing_disable_reason', 
            'action',
            'error',
            'new_disable_reason',
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        
        script_run_date = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        
        for account in accounts:
            account['script_run_date'] = script_run_date
            writer.writerow(account)
    
    
    logger.info(f"Report saved to {filename}")







def disable_account(token, user_id, email, days_old):

    url = f"{AUDIENCE}users/{user_id}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Create detailed disable reason
    now = datetime.now(timezone.utc)
    disable_reason = (
        f"Disabled by Daily_Disable_Accounts on {now.strftime('%Y-%m-%d')}: "
        f"Account inactive for {days_old} days (threshold: {MAXIMUM_DAYS} days)"
    )

    payload = {
        "blocked": True,
        "app_metadata": {
            "disable_reason": disable_reason, 
            "disabled_date": datetime.now(timezone.utc).isoformat(),
            "disabled_by": "Daily_Disable_Accounts_Script"

        }
    }

    try:
        response = requests.patch(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        logger.info(f"✓ Successfully disabled: {email}")
        return True, disable_reason
        
    except requests.HTTPError as e:
        logger.error(f"✗ Failed to disable {email}: {response.status_code} - {response.text}")
        return False, f"Failed: {e}"
    




def get_expired_accounts():
    execution_time = datetime.now(timezone.utc)
    execution_date = execution_time.strftime('%Y-%m-%d')
    execution_datetime = execution_time.strftime('%Y-%m-%d %H:%M:%S UTC')

    logger.info("=" * 70)
    logger.info("=== Starting Daily_Disable_Accounts Script ===")
    logger.info(f"=== Execution Date: {execution_datetime} ===") 
    logger.info(f"=== Mode: {'DRY RUN (no changes)' if DRY_RUN else 'LIVE (will disable)'} ===")
    logger.info(f"=== Policy: Disable accounts created after {POLICY_START.strftime('%Y-%m-%d')} that are older than {MAXIMUM_DAYS} days ===")
    logger.info("=" * 70)

    users = get_static_users()
    now = datetime.now(timezone.utc) #current utc time 

    # tracking counters
    total_users = 0
    before_policy = 0
    skipped_sso = 0
    skipped_linked = 0
    within_threshold = 0
    expired_found = 0
    successfully_disabled = 0
    failed_to_disable = 0

    # Lists for reporting
    expired_accounts = []
    disabled_accounts = []

    token = get_management_token() if not DRY_RUN else None

    logger.info("")
    logger.info("Processing users...")
    logger.info("")

    for user in users:
        total_users += 1
        email = user.get("email", "no-email")
        user_id = user.get("user_id", "unknown")

       # skip if already blocked
        if user.get("blocked", False):
            continue

        user_creation_date = user.get("created_at")
        if not user_creation_date:
            continue

        created_at = datetime.fromisoformat(user_creation_date.replace("Z", "+00:00"))
        
        # Check policy start date
        if created_at < POLICY_START:
            before_policy += 1
            logger.debug(f"Skipped (before policy): {email}")
            continue 

         # check for SSO
        identities = user.get("identities", [])
        connection_type = get_connection_type(identities)

        has_multiple_identities = len(identities) > 1

        if has_multiple_identities:
            skipped_linked += 1
            logger.info(f" SKIPPED (Linked Account): {email} - {len(identities)} identities")
            continue
        
        is_social = any(identity.get('isSocial', False) for identity in identities)

        # Skip SSO/linked accounts
        if is_social:
            skipped_sso += 1
            # logger.info(f" SKIPPED (SSO Connection): {email} - Connection: {connection_type}")
            continue

        # Calculate age
        acc_age_days = (now - created_at).days
        days_left = MAXIMUM_DAYS - acc_age_days


        if acc_age_days <= MAXIMUM_DAYS:
            within_threshold += 1
            
            # close to threshold
            if days_left <= 7 and days_left >= 0:
                logger.info("")
                logger.info(f"NOTICE: {email} will be disabled in {days_left} days")
                logger.info("")
            
            continue

        # to disable
        expired_found += 1

       # Get existing disable reason if any
        app_metadata = user.get("app_metadata", {})
        existing_reason = app_metadata.get("disable_reason", "Expired Account")
        

        logger.info(f" EXPIRED: {email} - {acc_age_days} days old (exceeds by {abs(days_left)} days)")
        logger.info(f"  Connection: {connection_type}")
        logger.info(f"  Existing disable_reason: {existing_reason}")
    


    # data for reporting
        account_data = {
            'email': email,
            'user_id': user_id,
            'created_at': created_at.strftime('%Y-%m-%d'),
            'days_old': acc_age_days,
            'days_over_threshold': abs(days_left),
            'connection_type': connection_type,
            'existing_disable_reason': existing_reason,
            'action': 'disables' if not DRY_RUN else 'would_disable'
        }
        
        expired_accounts.append(account_data)

        # Disable account (if not dry run)
        if DRY_RUN:
            logger.info(f"  [DRY RUN] Would disable this account")
        else:
            success, reason = disable_account(token, user_id, email, acc_age_days)
            
            if success:
                successfully_disabled += 1
                account_data['action'] = 'disabled'
                account_data['new_disable_reason'] = reason
            else:
                failed_to_disable += 1
                account_data['action'] = 'failed'
                account_data['error'] = reason
            
            disabled_accounts.append(account_data)
        
        logger.info("")

    # Summary Logging: 
    logger.info("=" * 70)
    logger.info("___ EXECUTION SUMMARY ___ ")
    logger.info("=" * 70)
    logger.info(f"Total users scanned: {total_users}")
    logger.info(f"   ─ Created before policy start: {before_policy}")
    logger.info(f"   ─ Linked accounts (protected): {skipped_linked}")
    logger.info(f"   ─ SSO/Linked accounts (skipped): {skipped_sso}")
    # logger.info(f"   ─ Within threshold ({MAXIMUM_DAYS} days): {within_threshold}")
    logger.info(f"   ─ Expired accounts: {expired_found}")
    logger.info("")
    
    if DRY_RUN:
        logger.info(f"[DRY RUN] Would have disabled: {expired_found} accounts")
    else:
        logger.info(f"Successfully disabled: {successfully_disabled}")
        if failed_to_disable > 0:
            logger.info(f"✗ Failed to disable: {failed_to_disable}")
    
    logger.info("=" * 70)





    #  SAVE REPORTS 
    if expired_accounts:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode = "dry_run" if DRY_RUN else "disabled"
        report_filename = f'accounts_{mode}_{timestamp}.csv'
        
        report_data = disabled_accounts if not DRY_RUN and disabled_accounts else expired_accounts
        save_report(report_data, report_filename)
    else:
        logger.info("No accounts met disable criteria - no report generated")

    logger.info("")
    logger.info("=== Script completed successfully ===")
    logger.info("=" * 70)


if __name__ == "__main__":
    try:
        get_expired_accounts()
    except KeyboardInterrupt:
        logger.warning("Script interrupted by user")
    except Exception as e:
        logger.exception(f"Script failed with error: {e}")
        raise    




