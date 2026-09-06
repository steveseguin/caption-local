from scripts.summarize_browser_load import summarize


def test_interrupted_capture_before_first_caption_stays_failed_without_crashing():
    run={'streams':1,'capture_seconds':60,'passed':False,'responses':[], 'interval':6,
         'observations':[{'seconds':5,'states':[{'buffered':5}]}],
         'final':[{'first_caption_seconds':None,'transcript':[],'buffered':0}]}
    samples=[{'seconds':0,'rss_mib':100,'cpu_seconds':0,'ready':True,'failed':0,'queue_timeouts':0},
             {'seconds':5,'rss_mib':100,'cpu_seconds':1,'ready':True,'failed':0,'queue_timeouts':0}]
    result=summarize(run,samples)
    assert not result['passed']
    assert result['first_caption_seconds'] is None
    assert not result['checks']['requested_capture_duration']
    assert not result['checks']['all_responses_successful']
