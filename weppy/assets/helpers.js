/*
    helpers.js
    ----------

    Javascript helpers for the weppy project.

    :copyright: (c) 2014-2016 by Marco Stagni
    :license: BSD, see LICENSE for more details.
*/
(function($,undefined) {

  var weppy;

  $.weppy = weppy = {
    ajax: function (_url, params, to, _type) {
      /*simple ajax function*/
      query = '';
      if(typeof params == "string") {
        serialized = $(params).serialize();
        if(serialized) {
          query = serialized;
        }
      } else {
        pcs = [];
        if(params != null && params != undefined)
          for(i = 0; i < params.length; i++) {
            q = $("[name=" + params[i] + "]").serialize();
            if(q) {
              pcs.push(q);
            }
          }
        if(pcs.length > 0) {
          query = pcs.join("&");
        }
      }
      $.ajax({
        type: _type ? _type : "GET",
        url: _url,
        data: query,
        success: function (msg) {
          if(to) {
            if(to == ':eval') {
              eval(msg);
            }
            else if(typeof to == 'string') {
              $("#" + to).html(msg);
            }
            else {
              to(msg);
            }
          }
        }
      });
    },

    loadComponents : function() {
      $('[data-wpp_remote]').each(function(index) {
          var f = function(obj) {
            var g = function(msg) {
              obj.html(msg);
            };
            return g;
          };
          $.weppy.ajax($(this).data("wpp_remote"),[], f($(this)), "GET");
      });
    }
  }

  $(function() {
    weppy.loadComponents();
  });

})($);

ajax = $.weppy.ajax;
