import sys
from collections import defaultdict
from wcwidth import wcswidth

# 均为了模拟toornment的结果，因为toornment不提供具体小分，以toornment为准
class TeamStats:
    def __init__(self, name):
        self.name = name
        self.match_points = 0
        self.small_points = 0
        self.opponents = []
        self.round_results = []  # (round_index, opponent, match_point, small_point)
        self.seed = None         # 初始种子顺位
    
    def __repr__(self):
        return self.name

def parse_input(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    team_names = []
    i = 0
    while not lines[i].isdigit():
        team_names.append(lines[i])
        i += 1

    team_stats = {}
    for seed, name in enumerate(team_names, start=1):
        team = TeamStats(name)
        team.seed = seed  # 保存初始种子顺位
        team_stats[name] = team

    rounds = []
    while i < len(lines):
        round_index = int(lines[i])
        i += 1
        matches = []
        while i < len(lines) and not lines[i].isdigit():
            team1, team2, score1, score2 = lines[i].split(',')
            matches.append((team1, team2, int(score1), int(score2)))
            i += 1
        rounds.append(matches)

    return team_stats, rounds

def process_rounds(team_stats, rounds):
    round_number = 0
    for matches in rounds:
        round_number += 1
        played = set()
        for team1, team2, score1, score2 in matches:
            played.add(team1)
            played.add(team2)
            win1 = 1 if score1 > score2 else 0
            win2 = 1 if score2 > score1 else 0
            team_stats[team1].match_points += win1
            team_stats[team1].small_points += (score1 - score2)
            team_stats[team1].opponents.append(team2)
            team_stats[team1].round_results.append((round_number, team2, win1, (score1 - score2)))

            team_stats[team2].match_points += win2
            team_stats[team2].small_points += (score2 - score1)
            team_stats[team2].opponents.append(team1)
            team_stats[team2].round_results.append((round_number, team1, win2, (score2 - score1)))

def compute_buchholz(team_stats):
    for team in team_stats.values():
        team.buchholz = sum(team_stats[opp].match_points for opp in team.opponents if opp)

# def compute_cumulative_opponent_points(team_stats, bye_value=0):
#     """计算每支队伍的 Cumulative Opponent Points (COP)，公式化实现。"""
#     for team in team_stats.values():
#         rounds_sorted = sorted(team.round_results, key=lambda x: x[0])
        
#         # 获取每轮对手的最终积分
#         mp_list = []
#         for _, opp, *rest in rounds_sorted:
#             if opp is None:  # 轮空
#                 mp_list.append(bye_value)
#             elif isinstance(opp, str):
#                 mp_list.append(getattr(team_stats.get(opp), "match_points", bye_value))
#             else:
#                 mp_list.append(getattr(opp, "match_points", bye_value))
        
#         R = len(mp_list)
#         # 直接用公式计算 COP
#         team.cop = sum((R - i) * mp for i, mp in enumerate(mp_list))

def compute_cumulative_scores(team_stats, rounds, bye_value_full=1, bye_value_half=0.5):
    """
    根据 FIDE 34E3 定义计算 cumulative score（累计得分表）。
    每个队伍会得到 team.cumulative_score (用于 COP 的计算)。
    """
    # 初始化
    for team in team_stats.values():
        team.cumulative_rounds = []  # 每轮累计大分
        team.cumulative_score = 0.0  # 总累计大分

    # 按轮次计算
    for round_idx, matches in enumerate(rounds, 1):
        for team in team_stats.values():
            # 找到该队伍这一轮的结果
            result = next((r for r in team.round_results if r[0] == round_idx), None)
            if result:
                _, _, mp, _ = result
                if mp == 1:
                    score = 1.0
                elif mp == 0:
                    score = 0.0
                else:
                    score = 0.5  # 支持平局
            else:
                # 没有对局，轮空
                score = 0.0

            prev = team.cumulative_rounds[-1] if team.cumulative_rounds else 0.0
            new_val = prev + score
            team.cumulative_rounds.append(new_val)

    # 计算 cumulative_score
    for team in team_stats.values():
        if len(team.cumulative_rounds) > 1:
            team.cumulative_score = sum(team.cumulative_rounds[:-1])
            # team.cumulative_score = sum(team.cumulative_rounds)
        else:
            team.cumulative_score = sum(team.cumulative_rounds)

        # 调整轮空分数
        for rnd, opp, mp, _ in team.round_results:
            if opp is None:
                if mp == 1:  # 全分轮空
                    team.cumulative_score -= bye_value_full
                elif mp == 0.5:  # 半分轮空
                    team.cumulative_score -= bye_value_half


def compute_cop(team_stats):
    """
    根据 FIDE 34E9 定义计算 COP（Cumulative scores of opposition）。
    COP = 所有对手 cumulative_score 之和
    """
    for team in team_stats.values():
        cop = 0.0
        for opp in team.opponents:
            if opp and opp in team_stats:
                cop += team_stats[opp].cumulative_score
        team.cop = cop

def compute_tiebreakers(team_stats, COP = True):
    sorted_teams = list(team_stats.values())

    def tiebreak_key(team):
        return (
            team.match_points,   # 总大分积分
            team.buchholz,       # 布赫霍尔茨
            team.small_points,   # 总小分
        )

    sorted_teams.sort(key=tiebreak_key, reverse=True)

    i = 0
    while i < len(sorted_teams):
        j = i
        while j < len(sorted_teams) and tiebreak_key(sorted_teams[i]) == tiebreak_key(sorted_teams[j]):
            j += 1

        group = sorted_teams[i:j]
        h2h_stats = {}

        if j - i > 1:
            for team in group:
                h2h_mp = 0
                h2h_sp = 0
                h2h_wins = 0
                h2h_sp_diff = 0
                for rnd, opp, mp, sp in team.round_results:
                    if opp in [t.name for t in group]:
                        h2h_mp += mp
                        h2h_sp += sp
                        if mp == 1:
                            h2h_wins += 1
                        h2h_sp_diff += sp
                h2h_stats[team.name] = (h2h_mp, h2h_sp, h2h_wins, h2h_sp_diff)
            if COP:
                group.sort(
                    key=lambda t: (
                        h2h_stats[t.name][0],  # H2H 大分
                        h2h_stats[t.name][1],  # H2H 小分
                        h2h_stats[t.name][2],  # 规则 4：大分胜场数
                        h2h_stats[t.name][3],  # 规则 5：小分差
                        t.cumulative_score,    # 累计对手分
                        -t.seed                # 初始种子顺位（seed 越小优先级越高）
                    ),
                    reverse=True
                )
            else:
                group.sort(
                    key=lambda t: (
                        h2h_stats[t.name][0],  # H2H 大分
                        h2h_stats[t.name][1],  # H2H 小分
                        h2h_stats[t.name][2],  # 规则 4：大分胜场数
                        h2h_stats[t.name][3],  # 规则 5：小分差
                        -t.seed                # 初始种子顺位（seed 越小优先级越高）
                    ),
                    reverse=True
                )
        else:
            team = group[0]
            h2h_stats[team.name] = (-1, -1, -1, -1)

        sorted_teams[i:j] = group
        for team in group:
            team.h2h_mp, team.h2h_sp, team.h2h_wins, team.h2h_sp_diff = h2h_stats[team.name]
        i = j

    return sorted_teams

def align_text(text, width):
    """对齐中英文混合字符串"""
    text = str(text)
    display_width = wcswidth(text)
    pad = width - display_width
    return text + " " * max(0, pad)

def print_standings(sorted_teams):
    headers = ["Rank", "Team", "Score", "Buchholz", "Map Diff", "H2H Score", "H2H MapDiff", "Cumulative", "seed"]
    widths = [5, 30, 10, 10, 10, 12, 15, 12, 6]

    header_line = "".join(align_text(h, w) for h, w in zip(headers, widths))
    print(header_line)

    for idx, team in enumerate(sorted_teams, 1):
        h2h_mp = getattr(team, 'h2h_mp', 0)
        h2h_sp = getattr(team, 'h2h_sp', 0)
        values = [
            idx, team.name, team.match_points, team.buchholz,
            team.small_points, h2h_mp, h2h_sp, team.cumulative_score, team.seed
        ]
        line = "".join(align_text(v, w) for v, w in zip(values, widths))
        print(line)
def generate_pairings(sorted_teams, previous_rounds):
    """
    生成下一轮对阵（Opposite pairing，避免重复对局，偶数优先组内对称配对，奇数下浮到下一组第一名）。
    输入：
      - sorted_teams: 按当前排名（从高到低）排序的 TeamStats 列表（每个对象有 .name, .match_points）
      - previous_rounds: 历史对局，list of rounds，每轮为[(team1, team2, score1, score2), ...]
    返回：
      - pairings: list of (teamA_name, teamB_name)；若轮空则为 ("TeamName", "BYE")
    """
    # 构建已对阵集合（名字排序的 tuple），用于快速查重
    played_pairs = set()
    for matches in previous_rounds:
        for t1, t2, _, _ in matches:
            # skip BYE 或 None
            if t1 and t2:
                played_pairs.add(tuple(sorted([t1, t2])))

    # 按得分分组（保持 sorted_teams 的组内次序）
    score_groups = {}
    for team in sorted_teams:
        score_groups.setdefault(team.match_points, []).append(team)

    # 由高分到低分处理
    pairings = []
    carry_over = None  # 从上一组“下浮”的队伍（若存在）

    for score in sorted(score_groups.keys(), reverse=True):
        group = score_groups[score].copy()  # 复制，避免污染原列表

        # 如果有上组下浮队伍，先把它与本组第一个可配对的队伍配对
        if carry_over:
            matched = False
            for idx, candidate in enumerate(group):
                key = tuple(sorted([carry_over.name, candidate.name]))
                if key not in played_pairs:
                    pairings.append((carry_over.name, candidate.name))
                    played_pairs.add(key)
                    group.pop(idx)
                    matched = True
                    break
            if not matched and group:
                # 如果本组所有人都曾打过该队，强制与本组第一个配对（按你的规则“顺延一位继续尝试”，此处选择最保守的 fallback）
                candidate = group.pop(0)
                pairings.append((carry_over.name, candidate.name))
                played_pairs.add(tuple(sorted([carry_over.name, candidate.name])))
            carry_over = None

        # 组内 Opposite pairing（用可变列表 indices = group_copy）
        indices = group[:]  # 直接元素为 TeamStats 对象
        while len(indices) > 1:
            t1 = indices[0]  # 当前要配对的“头部”队（第1名，或被上浮后的队）
            found_partner = False
            # 从尾部向中间寻找第一个未打过的对手
            for k in range(len(indices)-1, 0, -1):
                t2 = indices[k]
                key = tuple(sorted([t1.name, t2.name]))
                if key not in played_pairs:
                    # 找到可配对的对手
                    pairings.append((t1.name, t2.name))
                    played_pairs.add(key)
                    # 从 indices 中移除两个已配对队伍（先移后面的再移前面的保证索引正确）
                    indices.pop(k)
                    indices.pop(0)
                    found_partner = True
                    break
            if not found_partner:
                # t1 与组内所有剩余队都已经打过了 -> 下浮到下一组（carry_over）
                carry_over = indices.pop(0)
                # 继续尝试为剩下的队伍配对（不丢弃当前组的剩余）
                # 注意：不改变 played_pairs，这样剩下的队仍按规则继续配对

        # 若循环结束后 indices 中剩下 1 个队伍，则它将下浮到下一组
        if len(indices) == 1:
            carry_over = indices.pop(0)

    # 全部组处理完毕，如果还有 carry_over 就轮空（BYE）
    if carry_over:
        pairings.append((carry_over.name, "BYE"))

    return pairings


def main(file_path):
    team_stats, rounds = parse_input(file_path)
    process_rounds(team_stats, rounds)
    compute_buchholz(team_stats)
    compute_cumulative_scores(team_stats, rounds)
    compute_cop(team_stats)
    sorted_teams = compute_tiebreakers(team_stats)
    print_standings(sorted_teams)
    pairings = generate_pairings(sorted_teams, rounds)

    # 打印结果
    for a, b in pairings:
        print(f"{a}\t")
    print("="*160)
    for a, b in pairings:
        print(f"{b}\t")
    
    # sorted_teams = compute_tiebreakers(team_stats, COP=False)
    # print_standings(sorted_teams)

if __name__ == "__main__":
    main("/workspaces/result.txt")
