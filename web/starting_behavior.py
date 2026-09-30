"""Small advisory priors, never motor programs or kernel permissions."""

_GROUPS = (
    ({'bird', 'butterfly', 'bee', 'seagull', 'pelican', 'toy-airplane'},
     'Explore flowing flight with varied gentle curves, gliding and pauses; combine motion with wing poses.',
     ('flutter', 'flight', 'flap', 'glide', 'land')),
    ({'frog', 'rabbit', 'goat'},
     'Explore playful short hops with landing pauses and varied directions; avoid endless straight travel.',
     ('hop', 'land', 'look')),
    ({'fish', 'duck', 'turtle', 'dolphin', 'octopus', 'jellyfish'},
     'Explore flowing swimming or paddling, gentle turns, occasional dives and pauses.',
     ('swim', 'paddle', 'dive', 'leap', 'wiggle')),
    ({'cow', 'horse', 'pig', 'sheep', 'puppy', 'cat', 'hen', 'rooster'},
     'Explore short walks and turns between expressive poses and resting; vary pace rather than march forever.',
     ('walk', 'step', 'trot', 'look', 'chew', 'sniff', 'peck', 'wag')),
    ({'crab', 'starfish', 'shell'},
     'Explore small scuttles or wiggles with playful turns and pauses near the placed spot.',
     ('scuttle', 'wiggle', 'wave', 'open')),
    ({'tractor', 'scooter', 'skateboard', 'rover', 'robot', 'ball', 'yo-yo'},
     'Explore short rolling or bouncing runs, turning and pausing; vary direction and speed.',
     ('roll', 'bounce', 'lean', 'tilt', 'spin', 'beep')),
    ({'cloud', 'kite', 'balloon', 'frisbee', 'rocket', 'ufo', 'satellite', 'comet', 'astronaut', 'alien'},
     'Explore drifting, floating or soaring with curves and gentle speed changes between poses.',
     ('drift', 'sway', 'float', 'hover', 'orbit', 'thrust', 'spin', 'wave')),
    ({'flower', 'umbrella', 'hay-bale', 'sandcastle', 'scarecrow', 'pinwheel', 'jump-rope', 'hula-hoop', 'surfboard', 'teddy-bear', 'planet', 'moon', 'asteroid', 'space-station'},
     'Usually stay near the placed spot; explore expressive sways, turns and poses. Travel when the child invites it.',
     ('sway', 'wobble', 'spin', 'turn', 'wave', 'glow', 'wink', 'flag')),
)


def starting_behavior(asset, clips):
    """A new defensive bounded description using only declared visual clips."""
    tendency = 'Usually stay near the placed spot and explore expressive poses; follow the child when they invite travel.'
    preferred = ('wave', 'present', 'think', 'explain', 'talk', 'play')
    for assets, description, candidates in _GROUPS:
        if asset in assets:
            tendency, preferred = description, candidates
            break
    declared = set(clips)
    poses = [clip for clip in preferred if clip in declared][:3]
    return {'advisory': True, 'tendency': tendency, 'poses': poses,
            'precedence': 'Child direction and learned preferences override this starting tendency; choose only current offered keys.'}
