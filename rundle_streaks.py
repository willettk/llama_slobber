from llama_slobber.ll_rundles import get_rundles
from llama_slobber.ll_leagues import get_leagues
from llama_slobber.ll_rundle_members import get_rundle_personal, get_rundle_members

import re
import json
import os
import glob
import pandas as pd

CURRENT_SEASON = 104
LAST_VALID_SEASON = 82
DIV = '_Div_'
WILLETTK_ID = '17339'
LEVELS_NONROOKIE = list('ABCDE')
JSON_FILENAME = f'./streak_results/%s.json'
BAD_LEAGUE_NAMES = ['', '']
MAX_STREAK_LENGTH = CURRENT_SEASON - LAST_VALID_SEASON + 1



def get_clean_rundle_members(season, rundle):

    r = get_rundle_members(season, rundle)
    assert (r[0] == WILLETTK_ID) & (r[1] == ''), \
        f"Error: expected first two entries in rundle members to be " \
        f"{WILLETTK_ID} and '', but first five entries are {r[:5]}"

    return set(r[2:])

def get_all_leagues(overwrite_files=False):
    leagues = get_leagues(CURRENT_SEASON)
    #leagues = ['Saguaro', 'Geyser', 'Meridian',]
    verbose = False

    # Check if exists
    leagues_to_run = leagues.copy()
    for league_name in leagues:
        filename = JSON_FILENAME % league_name.lower()
        if os.path.exists(filename) and overwrite_files is False:
            print(f"{os.path.basename(filename)} exists and overwrite_files is False; "
            "skipping processing.")
            leagues_to_run.remove(league_name)
        if re.search('standings.php', league_name) or league_name == '':
            leagues_to_run.remove(league_name)

    return leagues_to_run

def get_streaks(league_name, verbose=False):

    league_exists = True

    # Create empty dicts
    continuous_membership = {}
    last_remaining_members = {}
    for level in LEVELS_NONROOKIE:
        key = f"{level}_{league_name}"
        continuous_membership[key] = set()
        last_remaining_members[key] = {}

    # Populate for the current season

    current_rundles = get_rundles(CURRENT_SEASON, league_name)
    for rundle in current_rundles:

        level_name = rundle.split(DIV)[0] if re.search(DIV, rundle) else rundle

        # It turns out that due to the way that `get_rundle_members` works,
        # the caller shows up in every single page.

        if not rundle.startswith('R'):
            current_season_rundle_members = get_clean_rundle_members(CURRENT_SEASON, rundle)
            if level_name in continuous_membership.keys():
                all_members = continuous_membership[level_name].union(current_season_rundle_members)
            else:
                all_members = current_season_rundle_members
            continuous_membership[level_name] = all_members

    # Begin looping over all available seasons for that league, starting with current season
    season = CURRENT_SEASON
    while league_exists:
        rundles = get_rundles(season, league_name)

        if len(rundles) != 0:
            print(f"Season {season:3}; {len(rundles):2} rundles in {league_name}")

            # Empty dict for all possible levels
            running_season = {}
            for level in LEVELS_NONROOKIE:
                running_season[f"{level}_{league_name}"] = set()

            # Get current members in each level, excluding Rookie
            for rundle in rundles:
                level_name = rundle.split(DIV)[0] if re.search(DIV, rundle) else rundle

                if not rundle.startswith('R'):

                    rundle_members_this_season = get_clean_rundle_members(season, rundle)
                    # Update with union
                    all_members = running_season[level_name].union(rundle_members_this_season)
                    running_season[level_name] = all_members

            # Check how many of the members in this season have been there since start

            for level_name, members_this_season in running_season.items():

                streakers = None
                if level_name in continuous_membership.keys():
                    members_since_start = continuous_membership[level_name]
                    streakers = members_this_season.intersection(members_since_start)
                    n_since_start = len(streakers)
                    if verbose:
                        print(f"Season {season}: Rundle {level_name} has {len(members_this_season)} "
                        f"members this season, and {n_since_start:2} members who have been in "
                        f"that level continuously since Season {CURRENT_SEASON}.")

                    continuous_membership[level_name] = streakers

                    # Compare to last season

                    if n_since_start == 0:
                        if 'season' not in last_remaining_members[level_name].keys():
                            last_remaining_members[level_name]['season'] = (season - 1)
                    else:
                        last_remaining_members[level_name]['members'] = streakers

            # Iterate season
            season -= 1
        else:
            # Stop when no results are found for a given year (assumes all leagues are continuous)
            league_exists = False


        # Manual break point until issue with shifting IDs is fixed
        if season == LAST_VALID_SEASON - 1:
            league_exists = False


    # Drop remaining members if streak is still active
    for level, v in last_remaining_members.items():
        if 'season' not in v.keys():
            _ = v.pop('members')

    # Structure to save results to file
    final_result = {}
    final_result['league'] = league_name
    final_result['longest_streak'] = {
        'streak_length': 0,
        'level': [],
    }
    final_result['streaks'] = []

    # Calculate best streaks per level and print to screen
    for i,level in enumerate(sorted(list(last_remaining_members.keys()))):
        dl = {}

        l = last_remaining_members[level]
        c = continuous_membership[level]
        assert (l == {}) ^ (len(c) == 0), \
            f"Error for level {level}: {l}, {c}"
        if l == {}:
            streakers = c
            streak_length = CURRENT_SEASON - season
            last_season = season + 1
        elif len(c) == 0:
            streakers = l['members']
            streak_length = CURRENT_SEASON - l['season'] + 1
            last_season = l['season']

        s_sfx = ' ' if len(streakers) == 1 else 's'
        ssn_sfx = ' ' if streak_length == 1 else 's'
        print(f"{level} has {len(streakers):2} member{s_sfx} with an active streak of "
        f"{streak_length} season{ssn_sfx} from Season {CURRENT_SEASON} to Season {last_season}. ")

        # Save to JSON file
        dl['rundle'] = level
        dl['level'] = level[0]
        dl['n_streakers'] = len(streakers)
        dl['streak_length'] = streak_length
        dl['streak_start'] = last_season
        dl['streak_end'] = CURRENT_SEASON
        dl['streakers'] = list(streakers)
        final_result['streaks'].append(dl)

    max_streak = 0
    for streak in final_result['streaks']:
        sl = streak['streak_length']
        level = streak['level']
        if streak['streak_length'] > max_streak:
            final_result['longest_streak']['streak_length'] = sl
            final_result['longest_streak']['level'] = [level, ]
            max_streak = sl
        elif streak['streak_length'] == max_streak:
            final_result['longest_streak']['level'].append(level)


    with open(JSON_FILENAME % league_name.lower(),'w') as f:
        json.dump(final_result, f, indent=4)

    return final_result


def check_max_streaks(level='A'):

    files = glob.glob("./streak_results/*json")

    leagues = []
    streakers = []
    for f in files:
        with open(f,'r') as fn:
            d = json.load(fn)
        basename = os.path.basename(f).split('.')[0].capitalize()
        if (d['longest_streak']['streak_length'] == MAX_STREAK_LENGTH) & (level in d['longest_streak']['level']):
            #print(f"{basename:20}: {d['streaks'][0]['n_streakers']}")
            leagues.append(basename)
            streakers.append(d['streaks'][LEVELS_NONROOKIE.index(level)]['n_streakers'])

    df = pd.DataFrame(data=streakers, index=leagues, columns=['n_streakers',])

    return df

if __name__ == "__main__":

    """
    leagues = get_all_leagues()

    for league in leagues:
        _ = get_streaks(league)
    """

    for level in LEVELS_NONROOKIE:
        df = check_max_streaks(level)
        print(f"There are {df['n_streakers'].sum():3} players in {level} with an active "
        f"level+rundle streak of at least {MAX_STREAK_LENGTH} seasons.")

    dfb = check_max_streaks('B')
    print(dfb)

# Issue: starting in Season 81, the user IDs for some reason go from numbers to usernames. 
# This means I can't keep track earlier than that unless I have a mapping. 
# Looks like it might be possible to fix if I can get a different parser