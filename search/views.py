from django.shortcuts import render
from search.models import ArticleType
import json
from django.views.generic.base import View
from django.http import HttpResponse
from elasticsearch import Elasticsearch
from datetime import datetime

import redis
redis_cli = redis.StrictRedis(host="localhost",charset="UTF-8",decode_responses=True)

# Create your views here.
# fuzzy  vague search

#import redis

client = Elasticsearch(hosts=["127.0.0.1"])
#redis_cli = redis.StrictRedis()


class IndexView(View):
    #首页
    def get(self, request):
        topn_search = redis_cli.zrevrangebyscore("search_keywords_set", "+inf", "-inf", start=0, num=5)
        return render(request, "index.html", {"topn_search":topn_search})

# Create your views here.重载
class SearchSuggest(View):
    def get(self, request):

        #s_type = request.GET.get("s_type","article")

        key_words = request.GET.get('s','')  # index.html pass s, default is black
        re_datas = []  # multiple key words
        if key_words:
            s = ArticleType.search()
            s = s.suggest('my_suggest', key_words, completion={
                "field":"suggest", "fuzzy":{
                    "fuzziness":2,
                    #"transpositions": "False"
                },
                "size": 10
            })
            suggestions = s.execute_suggest()
            for match in suggestions.my_suggest[0].options:
                source = match._source
                re_datas.append(source["title"])
        return HttpResponse(json.dumps(re_datas), content_type="application/json")


class SearchView(View):
    def get(self, request):
        key_words = request.GET.get("q","")
        s_type = request.GET.get("s_type", "article")

        redis_cli.zincrby("search_keywords_set", key_words)

        topn_search = redis_cli.zrevrangebyscore("search_keywords_set", "+inf", "-inf", start=0, num=5)

        page = request.GET.get("p", "1")
        #must be int
        try:
            page = int(page)
        except:
            page = 1

        jobbole_count = redis_cli.get("jobbole_count")

        start_time = datetime.now()
        #from 0 page

        response = client.search(
            index= "jobbole",
            body={
                "query":{
                    "multi_match":{
                        "query":key_words,
                        "fields":["tags", "title", "content"]
                    }
                },
                "from":(page-1)*10,
                "size":10,
                "highlight": {
                    "pre_tags": ['<span class="keyWord">'],
                    "post_tags": ['</span>'],
                    "fields": {
                        "title": {},
                        "content": {},
                    }
                }
            }
        )

        end_time = datetime.now()
        last_seconds = (end_time-start_time).total_seconds()  #calculate total time

        total_nums = response["hits"]["total"]

        if (page%10) > 0:
            page_nums = int(total_nums/10) +1
        else:
            page_nums = int(total_nums/10)


        hit_list = []
        for hit in response["hits"]["hits"]:
            hit_dict = {}
            if "title" in hit["highlight"]:  # title in html format highlight in here
                hit_dict["title"] = "".join(hit["highlight"]["title"])  #array will be together
            else:
                hit_dict["title"] = hit["_source"]["title"]
            if "content" in hit["highlight"]:
                hit_dict["content"] = "".join(hit["highlight"]["content"])[:500]
            else:
                hit_dict["content"] = hit["_source"]["content"][:500] # limit on page

            hit_dict["create_date"] = hit["_source"]["create_date"]
            hit_dict["url"] = hit["_source"]["url"]
            hit_dict["score"] = hit["_score"]

            hit_list.append(hit_dict)

        return render(request, "result.html", {"page":page,
                                               "all_hits":hit_list,
                                               "key_words":key_words,
                                               "total_nums":total_nums,
                                               "page_nums":page_nums,
                                               "last_seconds":last_seconds,
                                               "jobbole_count":jobbole_count,
                                               "topn_search":topn_search})
